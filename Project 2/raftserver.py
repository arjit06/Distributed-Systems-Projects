import json
import os
from threading import Lock
import threading
import time
import random
from typing import Optional, Dict
import grpc
from concurrent import futures

# Import the generated classes from raft.proto
import raft_pb2
import raft_pb2_grpc

import logging


class LogEntry:
    def __init__(self, term, command):
        self.term = term
        self.command = command


class NodeState:
    def __init__(self, node_id, storage_dir):
        self.node_id = node_id
        self.storage_dir = storage_dir
        self.current_term = 0
        self.voted_for = None
        self.log = []  # This will hold LogEntry objects
        self.commit_index = 0
        self.last_applied = 0
        self.next_index = {}
        self.match_index = {}
        self.leader_lease_end = None  # Timestamp indicating when the leader lease ends
        self.lock = Lock()  # To protect concurrent access to node state

        # Set up the logger
        self.logger = logging.getLogger(f'NodeState{self.node_id}')
        file_handler = logging.FileHandler(os.path.join(
            storage_dir, f'dump_node_{self.node_id}.txt'))
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(file_handler)
        self.logger.setLevel(logging.INFO)

        self.load_state()

    def persist_state(self):
        # Persist the state to a JSON file for simplicity
        with self.lock:
            state_file = os.path.join(
                self.storage_dir, f'state_node_{self.node_id}.json')
            with open(state_file, 'w') as f:
                json.dump({
                    'current_term': self.current_term,
                    'voted_for': self.voted_for,
                    'log': [{'term': entry.term, 'command': entry.command} for entry in self.log],
                    'commit_index': self.commit_index,
                    'last_applied': self.last_applied,
                    'leader_lease_end': self.leader_lease_end
                }, f, indent=4)

    def parse_command(self, command):
        # Parse the command string and return the command type, key, and value
        parts = command.split()
        command_type = parts[0]
        key = parts[1] if len(parts) > 1 else None
        value = parts[2] if len(parts) > 2 else None
        return command_type, key, value

    def update_term(self, term, candidate_id=None):
        with self.lock:
            if term > self.current_term:
                self.current_term = term
                self.voted_for = candidate_id  # Update voted_for if provided
                self.persist_state()

    def add_entry(self, entry: LogEntry):
        with self.lock:
            self.log.append(entry)
            self.logger.info(
                f"Log entry added: {entry.command} with term {entry.term}")
            self.persist_state()  # Persist state after adding entry

    def apply_entry_to_state_machine(self, index):
        with self.lock:
            if index <= len(self.log) and index > self.last_applied:
                entry = self.log[index - 1]  # Log index starts at 1
                command_type, key, value = self.parse_command(entry.command)
                self.logger.info(
                    f"Applying log entry to state machine: {entry.command}")

                if command_type == 'SET':
                    # If it's a SET command, we update the key-value store
                    self.state_machine[key] = value
                elif command_type == 'GET':
                    # If it's a GET command, we retrieve the value (not typically "applied" but included for completeness)
                    return self.state_machine.get(key, '')
                elif command_type == 'DELETE':
                    # If it's a DELETE command, we remove the key from the store
                    self.state_machine.pop(key, None)
                # ... handle other command types as needed

                self.last_applied = index
                self.persist_state()

    def load_state(self):
        # Load the state from disk if it exists
        state_file = os.path.join(
            self.storage_dir, f'metadata_{self.node_id}.json')
        if os.path.isfile(state_file):
            with open(state_file, 'r') as f:
                state_data = json.load(f)
                self.current_term = state_data['current_term']
                self.voted_for = state_data['voted_for']
                self.log = [LogEntry(entry['term'], entry['command'])
                            for entry in state_data['log']]
                self.commit_index = state_data['commit_index']
                self.last_applied = state_data['last_applied']
                self.leader_lease_end = state_data.get('leader_lease_end')

            self.logger.info("State loaded from disk.")


def save_state_to_disk(node_state: NodeState, file_path="node_state.json"):
    # Convert the node state to a dictionary for JSON serialization
    state_dict = {
        "node_id": node_state.node_id,
        "current_term": node_state.current_term,
        "voted_for": node_state.voted_for,
        # Assume LogEntry has a method to convert it to a dict or similar serializable form
        "log": [entry.to_dict() for entry in node_state.log],
        "commit_index": node_state.commit_index,
        "last_applied": node_state.last_applied,
        "leader_lease_end": node_state.leader_lease_end
    }
    with open(file_path, 'w') as f:
        json.dump(state_dict, f)


def load_state_from_disk(file_path="node_state.json") -> NodeState:
    with open(file_path, 'r') as f:
        state_dict = json.load(f)
    node_state = NodeState(node_id=state_dict["node_id"])
    node_state.current_term = state_dict["current_term"]
    node_state.voted_for = state_dict["voted_for"]
    # Assume LogEntry has a constructor or method for creating instances from dicts
    node_state.log = [LogEntry.from_dict(entry) for entry in state_dict["log"]]
    node_state.commit_index = state_dict["commit_index"]
    node_state.last_applied = state_dict["last_applied"]
    node_state.leader_lease_end = state_dict["leader_lease_end"]
    return node_state


class RaftServer:

    logger = logging.getLogger(__name__)

    def __init__(self, state: NodeState, peers: Dict[str, str]):
        self.state = state
        self.peers = peers  # Other nodes' identifiers in the cluster
        self.lock = threading.Lock()
        self.election_timeout = self.get_random_election_timeout()
        self.heartbeat_interval = 1
        self.lease_duration = 2.5
        self.stop_event = threading.Event()
        self.election_timer = threading.Timer(
            self.election_timeout, self.start_election)
        self.heartbeat_timer = None  # Heartbeat timer is started only if node is leader

        self.logger.setLevel(logging.INFO)
        file_handler = logging.FileHandler(f'dump_node_{state.node_id}.txt')
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s: %(message)s'))
        self.logger.addHandler(file_handler)

        self.leader_id: Optional[str] = None

    def get_random_election_timeout(self):
        return random.uniform(5, 10)

    def get_peer_address(self, peer_id):
        return self.peer_addresses.get(peer_id)

    def reset_election_timer(self):

        if self.election_timer.is_alive():
            self.election_timer.cancel()
        self.election_timeout = self.get_random_election_timeout()
        self.election_timer = threading.Timer(
            self.election_timeout, self.start_election)
        self.logger.info(f"Node {self.state.node_id} reset election timer.")
        self.election_timer.start()

    def handle_get(self, key):
        # Logic to retrieve the value for 'key' from the state machine
        # This might involve just looking up the key in a local dictionary
        # assuming the state machine is a simple key-value store
        value = self.state_machine.get(key, "")
        success = True if key in self.state_machine else False
        return value, success

    def handle_set(self, key, value):
        # Logic to set the value for 'key' in the state machine
        # In a real Raft implementation, this would involve appending a new
        # log entry and replicating it to the follower nodes
        if self.is_leader():
            self.append_to_log(key, value)
            return True
        else:
            return False

    def renew_lease(self):
        if self.is_leader():
            self.logger.info(f"Leader {self.state.node_id} renewed its lease.")
            self.state.leader_lease_end = time.time() + self.lease_duration
            # When sending AppendEntries, include the new lease_end timestamp
            for peer_id in self.peers:
                if peer_id != self.state.node_id:
                    self.send_append_entries(
                        peer_id, entries=[], leader_commit=self.state.commit_index)

    def check_lease(self):
        # This would likely be called before serving read requests to ensure the lease is still valid
        if not self.is_leader() or time.time() > self.state.leader_lease_end:
            return False  # Lease is not valid
        return True  # Lease is valid

    def send_heartbeats(self):
        with self.lock:
            if not self.is_leader():
                return  # Only the leader sends heartbeats
            print(f"Leader {self.state.node_id} sending heartbeats.")
            self.logger.info(
                f"Leader {self.state.node_id} sending heartbeat & Renewing Lease")
            # Example heartbeat logic, assuming a method to send AppendEntries RPC
            for peer_id in self.peers:
                if peer_id != self.state.node_id:
                    # Send a heartbeat (an AppendEntries RPC with no log entries) to each peer
                    self.send_append_entries(
                        peer_id, entries=[], leader_commit=self.state.commit_index)
            # Schedule the next heartbeat
            self.heartbeat_timer = threading.Timer(
                self.heartbeat_interval, self.send_heartbeats)
            self.heartbeat_timer.start()

    def become_leader(self):
        with self.lock:
            print(
                f"Node {self.state.node_id} became the leader for term {self.state.current_term}.")
            self.logger.info(
                f"Node {self.state.node_id} became the leader for term {self.state.current_term}.")
            self.state.votes_received = set()  # Clear votes as they are no longer needed
            self.leader_id = self.state.node_id  # Officially become the leader
            self.initialize_leader_state()  # Initialize leader-specific state variables

            # Start sending heartbeats immediately upon becoming the leader
            if self.heartbeat_timer is not None:
                self.heartbeat_timer.cancel()
            self.send_heartbeats()

    def start_election(self):
        with self.lock:
            # Transition to candidate state
            self.state.update_term(self.state.current_term + 1)
            self.state.voted_for = self.state.node_id
            self.leader_id = None
            print(
                f"Node {self.state.node_id} starting election for term {self.state.current_term}")
            self.logger.info(
                f"Node {self.state.node_id} election timer timed out, Starting election.")
            # Vote for self
            self.state.votes_received = set([self.state.node_id])

            # Reset election timer
            self.election_timer.cancel()
            self.election_timer = threading.Timer(
                self.election_timeout, self.start_election)
            self.election_timer.start()

            # Send RequestVote RPCs to all other nodes
            for peer_id in self.peers:
                if peer_id != self.state.node_id:
                    self.send_request_vote(peer_id)

    def send_request_vote(self):
        with self.lock:
            self.logger.info(
                f"Node {self.state.node_id} sent a vote request to all peers.")

            last_log_index = len(self.state.log) - 1
            last_log_term = self.state.log[last_log_index].term if self.state.log else 0
            vote_count = 1  # Start with vote for self
            self.state.voted_for = self.state.node_id
            self.state.persist_state()

            for peer_id, address in self.peers.items():
                if peer_id == self.state.node_id:
                    continue  # Skip self
                try:
                    with grpc.insecure_channel(address) as channel:
                        stub = raft_pb2_grpc.RaftServiceStub(channel)
                        response = stub.RequestVote(raft_pb2.RequestVoteArgs(
                            term=self.state.current_term,
                            candidate_id=self.state.node_id,
                            last_log_index=last_log_index,
                            last_log_term=last_log_term
                        ))
                        if response.vote_granted:
                            vote_count += 1
                            if vote_count > len(self.peers) // 2:
                                self.become_leader()
                                return  # Exit early if majority vote achieved
                        elif response.term > self.state.current_term:
                            self.state.update_term(response.term)
                            break  # Break if we find a higher term
                except grpc.RpcError as e:
                    print(f"Failed to send RequestVote to {peer_id}: {e}")

    def initialize_leader_state(self):
        with self.lock:
            # Set next_index for each follower to the index just after the last one in the leader's log
            last_log_index = len(self.state.log)
            self.state.next_index = {
                peer_id: last_log_index + 1 for peer_id in self.peers}

            # Reset match_index for each follower to 0, since the leader doesn't know the highest log entry
            # replicated on the followers yet
            self.state.match_index = {peer_id: 0 for peer_id in self.peers}

    def send_append_entries(self, peer_id, entries, leader_commit):
        peer_address = self.get_peer_address(peer_id)
        if not peer_address:
            print(f"No address found for peer {peer_id}.")
            return

        # Prepare the entries for gRPC call
        grpc_entries = [raft_pb2.LogEntry(
            command=e.command, term=e.term) for e in entries]

        # Create the gRPC request
        request = raft_pb2.AppendEntriesArgs(
            term=self.state.current_term,
            leader_id=self.state.node_id,
            prev_log_index=self.state.next_index[peer_id] - 1,
            prev_log_term=self.state.log[self.state.next_index[peer_id] -
                                         2].term if self.state.next_index[peer_id] > 1 else 0,
            entries=grpc_entries,
            leader_commit=leader_commit
        )

        # Make the gRPC call
        with grpc.insecure_channel(peer_address) as channel:
            stub = raft_pb2_grpc.RaftServiceStub(channel)
            try:
                response = stub.AppendEntries(request)
                print(f"Received response from {peer_id}: {response.success}")
            except grpc.RpcError as e:
                print(f"Failed to send AppendEntries to {peer_id}: {e}")

    def on_receive_vote_request(self, term, candidate_id, last_log_index, last_log_term):
        vote_granted = False
        with self.lock:
            # Check if term is at least as large as the node's current term
            if term >= self.state.current_term:
                # Update term if the incoming term is greater
                if term > self.state.current_term:
                    self.state.update_term(term)
                    self.state.voted_for = None

                # Check log up-to-dateness: first by term, then by index
                last_own_log_term = self.state.log[-1].term if self.state.log else 0
                last_own_log_index = len(self.state.log) - 1
                log_is_at_least_as_up_to_date = (
                    last_log_term > last_own_log_term or
                    (last_log_term == last_own_log_term and last_log_index >=
                     last_own_log_index)
                )

                if (self.state.voted_for is None or self.state.voted_for == candidate_id) and log_is_at_least_as_up_to_date:
                    self.state.voted_for = candidate_id
                    self.state.persist_state()
                    vote_granted = True

            if (vote_granted):
                self.logger.info(
                    f"Vote granted for Node {candidate_id} in term {term}.")
            else:
                self.logger.info(
                    f"Vote denied for Node {candidate_id} in term {term}.")

            return {'term': self.state.current_term, 'voteGranted': vote_granted}

    def on_receive_append_entries(self, term, leader_id, prev_log_index, prev_log_term, entries, leader_commit):
        success = False
        with self.lock:
            # Reply false if term < current term
            if term < self.state.current_term:
                return {'term': self.state.current_term, 'success': success}

            # Reset election timer here because a valid leader exists
            self.reset_election_timer()

            # Update current term, switch to follower state if term > current term
            if term > self.state.current_term:
                self.state.update_term(term)
                self.leader_id = leader_id  # Recognize the leader

            # Check if log contains entry at prev_log_index whose term matches prev_log_term
            if prev_log_index < len(self.state.log) and self.state.log[prev_log_index].term == prev_log_term:
                success = True
                # Insert entries not already in the log
                insert_position = prev_log_index + 1
                for entry in entries:
                    if insert_position < len(self.state.log):
                        # Conflict resolution
                        if self.state.log[insert_position].term != entry.term:
                            self.state.log = self.state.log[:insert_position]
                            self.state.log.append(entry)
                    else:
                        self.state.log.append(entry)
                    insert_position += 1

                # Update commit index
                if leader_commit > self.state.commit_index:
                    self.state.commit_index = min(
                        leader_commit, len(self.state.log) - 1)
                    # Apply newly committed entries to the state machine

                self.state.persist_state()

            if success:
                self.logger.info(
                    f"Node {self.state.node_id} accepted AppendEntries RPC from {leader_id}.")
            else:
                self.logger.info(
                    f"Node {self.state.node_id} rejected AppendEntries RPC from {leader_id}.")

            return {'term': self.state.current_term, 'success': success}

    def is_leader(self):
        return self.leader_id == self.state.node_id

    def stop(self):
        with self.lock:
            self.stop_event.set()
            self.logger.info(f"Node {self.state.node_id} is stopping.")
            if self.election_timer:
                self.election_timer.cancel()
            if self.heartbeat_timer:
                self.heartbeat_timer.cancel()

    def run(self):
        self.logger.info(f"Node {self.state.node_id} is starting.")
        self.election_timer.start()


class RaftService(raft_pb2_grpc.RaftServiceServicer):

    def __init__(self, raft_server):
        self.raft_server = raft_server

    def ServeClient(self, request, context):
        # Handle client requests to the Raft cluster
        if request.request.startswith("GET"):
            key = request.request.split()[1]
            value, success = self.raft_server.handle_get(key)
            return raft_pb2.ServeClientReply(data=value, success=success, leader_id=self.raft_server.leader_id)
        elif request.request.startswith("SET"):
            _, key, value = request.request.split()
            success = self.raft_server.handle_set(key, value)
            return raft_pb2.ServeClientReply(success=success, leader_id=self.raft_server.leader_id)
        else:
            return raft_pb2.ServeClientReply(success=False, leader_id=self.raft_server.leader_id)

    def AppendEntries(self, request, context):
        # Implementation of the AppendEntries RPC for log replication
        success, term = self.raft_server.on_receive_append_entries(
            term=request.term,
            leader_id=request.leader_id,
            prev_log_index=request.prev_log_index,
            prev_log_term=request.prev_log_term,
            entries=request.entries,
            leader_commit=request.leader_commit
        )
        return raft_pb2.AppendEntriesReply(term=term, success=success)

    def RequestVote(self, request, context):
        # Implementation of the RequestVote RPC for leader election
        vote_granted, term = self.raft_server.on_receive_vote_request(
            term=request.term,
            candidate_id=request.candidate_id,
            last_log_index=request.last_log_index,
            last_log_term=request.last_log_term
        )
        return raft_pb2.RequestVoteReply(term=term, vote_granted=vote_granted)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    raft_pb2_grpc.add_RaftServiceServicer_to_server(RaftService(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    server.wait_for_termination()


if __name__ == '__main__':
    serve()
