import json
import os
from threading import Lock
import threading
import time
import random
from typing import Optional, Dict
import grpc
from concurrent import futures

import grpc
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
        if not os.path.exists(f"logs_node_{self.node_id}"):
            os.makedirs(f"logs_node_{self.node_id}")
        self.state_machine = {}  # Simple key-value store to act as the state machine

        # Set up the logger
        self.logger = logging.getLogger(f'NodeState{self.node_id}')
        file_handler = logging.FileHandler(os.path.join(
            storage_dir, f'dump_node_{self.node_id}.txt') , mode='a')
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(file_handler)
        self.logger.setLevel(logging.INFO)
        self.known_leader_lease_end = 0

        self.log_file_path=f"logs_node_{self.node_id}/logs.txt"
        

        self.load_state()

    def persist_state(self):
        # Persist the state to a JSON file for simplicity
        state_file = os.path.join(
            self.storage_dir, f'metadata_{self.node_id}.json')

        with open(state_file, 'w') as f:
            json.dump({
                'current_term': self.current_term,
                'voted_for': self.voted_for,
                'log': [{'term': entry.term, 'command': entry.command} for entry in self.log],
                'commit_index': self.commit_index,
                'last_applied': self.last_applied,
                'leader_lease_end': self.leader_lease_end,
                'state_machine': self.state_machine
            }, f, indent=4)

            
    def parse_command(self, command):
        
        # Parse the command string and return the command type, key, and value
        parts = command.split()
        command_type = parts[0]
        key = parts[1] if len(parts) > 1 else None
        value = parts[2] if len(parts) > 2 else None
        return command_type, key, value

    def update_term(self, term, candidate_id=None):

        # with self.lock:

            if term > self.current_term:
                self.current_term = term
                self.voted_for = candidate_id  # Update voted_for if provided
                self.persist_state()

    def add_entry(self, entry: LogEntry,cmd):
            
        # with self.lock:
            self.log.append(entry)
            self.append_to_logfile(cmd)
            # self.logger.info(
            #     f"Log entry added: {entry.command} with term {entry.term}")
            self.persist_state()  # Persist state after adding entry

    def append_to_logfile(self,command):
        with open(self.log_file_path, 'a') as f:
            f.write(f"{command} {self.current_term}\n")
        

    def apply_entry_to_state_machine(self, index):
        # with self.lock:
        try:
            # print("inside apply entry: LastApplied:",self.last_applied)
            # print("inside apply entry: CommitIndex:",index)
            if index <= len(self.log) and index > self.last_applied:
                # print("I am here2")
                entry = self.log[self.last_applied]  # Log index starts at 1
                command_type, key, value = self.parse_command(entry.command)
                self.logger.info(
                    f"Node {self.node_id} committed the entry {entry.command} to state machine")
                

                if command_type == 'SET':
                    # If it's a SET command, we update the key-value store
                    self.state_machine[key] = value
                elif command_type == 'GET':
                    # If it's a GET command, we retrieve the value (not typically "applied" but included for completeness)
                    return self.state_machine.get(key, '')



                self.last_applied +=1
                self.persist_state()
        except Exception as e:
            print(e)

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
                self.state_machine=state_data["state_machine"]
                # 'state_machine': self.state_machine

            # self.logger.info("State loaded from disk.")



# All Nodes are Servers [Leader/Candiate/Follower]
class RaftServer:

    logger = logging.getLogger(__name__)

    def __init__(self, state: NodeState, peers: Dict[str, str]):
        self.state = state
        self.peers = peers  # Other nodes' identifiers in the cluster
        self.lock = threading.Lock()
        self.election_timeout = self.get_random_election_timeout()
        self.heartbeat_interval = 1
        self.lease_duration = 6
        self.stop_event = threading.Event()
        self.election_timer = threading.Timer(
            self.election_timeout, self.start_election)
        
        self.heartbeat_timer = None  # Heartbeat timer is started only if node is leader
        # self.entries=[]
        
        self.logger.setLevel(logging.INFO)
        file_handler = logging.FileHandler(
            os.path.join(self.state.storage_dir, f'dump_node_{self.state.node_id}.txt'), mode='a')
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s: %(message)s'))
        self.logger.addHandler(file_handler)

        self.leader_id = None
        self.leader_lease_end = None
        self.election_timer.start()
        self.set_request_result=None
        
        
        
    def is_leader(self):
        return self.leader_id == self.state.node_id

    def step_down(self):
        time.sleep(self.leader_lease_end-time.time())
        if self.election_timer.is_alive():
            self.election_timer.cancel()
        self.election_timeout = self.get_random_election_timeout()
        self.election_timer = threading.Timer(
            self.election_timeout, self.start_election)
        self.logger.info(f"Node {self.state.node_id} stepping down")
        self.leader_id=None
        self.election_timer.start()
        

        
        

    def get_random_election_timeout(self):
        return random.uniform(5, 10)

    def get_peer_address(self, peer_id):
        return self.peers.get(peer_id)

    def reset_election_timer(self):

        if self.election_timer.is_alive():
            self.election_timer.cancel()
        self.election_timeout = self.get_random_election_timeout()
        self.election_timer = threading.Timer(
            self.election_timeout, self.start_election)
        # self.logger.info(f"Node {self.state.node_id} reset election timer.")
        self.election_timer.start()
    
    def renew_leader_lease(self):
        # The leader renews its lease
        if self.is_leader():
            self.leader_lease_end = time.time() + self.lease_duration
            self.logger.info(f"Leader {self.state.node_id} renewed lease until {self.leader_lease_end}")
            
    def check_leader_lease_valid(self):
        # Before serving read requests, the leader checks if the lease is still valid
        return time.time() < self.leader_lease_end if self.leader_lease_end else False


        
    def handle_get(self, key,cmd):
        # Logic to retrieve the value for 'key' from the state machine
        # This might involve just looking up the key in a local dictionary
        # assuming the state machine is a simple key-value store
        
        # if self.is_leader():
        self.logger.info(f"Node {self.state.node_id} received an {cmd} request")
        value = self.state.state_machine.get(key, "")
        success = True if key in self.state.state_machine else False
        if(not success):
            value=""
        return value, success
        # else:
        #     return -1, False
    

    def handle_set(self, key, value,cmd):
        # Logic to set the value for 'key' in the state machine
        # In a real Raft implementation, this would involve appending a new
        # log entry and replicating it to the follower nodes
        

        
        # if self.is_leader():
        self.logger.info(f"Node {self.state.node_id} received an {cmd} request")
        new_entry = LogEntry(term=self.state.current_term, command=cmd)
        a=self.state.commit_index
        
        self.state.add_entry(new_entry,cmd)
        time.sleep(1.5)
        b=self.state.commit_index
        if(b>a):

            return True
        else:
            return False
        # else:
        #     return False
    
        
        
    def on_receive_append_entries(self, term, leader_id, prev_log_index, prev_log_term, entries, leader_commit,leader_lease_duration):
        try:
            success = False
            # with self.lock:
            # Reply false if term < current term
            self.state.known_leader_lease_end = leader_lease_duration
            if term < self.state.current_term:
                self.logger.info(
                    f"Node {self.state.node_id} rejected AppendEntries RPC from {leader_id}.")
                
                # print("Follower is ahead")
                return success , self.state.current_term
                # return {'term': self.state.current_term, 'success': success}

            # Reset election timer here because a valid leader exists
            self.reset_election_timer()
            
            # Persist state --> did notunderstand / is it commit or something else ?
            # How is leader_id updated after first Append entry after leader wins election
            # if term==self.state.current_term and leader_id!=self.leader_id:
            self.leader_id=leader_id
            
            # Update current term, switch to follower state if term > current term
            if term > self.state.current_term:
                self.state.update_term(term)
                # self.leader_id = leader_id  # Recognize the leader
                
            # print(len(entries),type(entries))
            # try:
            #     for a in entries:
            #         # print(f"first_time:{a.command}")
            # except Exception as e:
            #       print(e)
            # print("done\n")
            # if it is a heartbeat message then log will be empty so we do not need to check for the prev_log_index and prev_log_term
            if len(entries) == 0:
                
                success = True
                self.logger.info(
                    f"Node {self.state.node_id} accepted AppendEntries RPC from {leader_id}.")
                self.state.persist_state()
                if leader_commit > self.state.commit_index:
                    self.state.commit_index = min(
                        leader_commit, len(self.state.log)) # chat gpt says -1
                    # Apply newly committed entries to the state machine
                    
                    while (self.state.last_applied < self.state.commit_index):
                        # print(f"inside while Commit Index: {self.state.commit_index}")
                        # print(f"inside while Last Applied: {self.state.last_applied}")
                        # print("I am here")
                        self.state.apply_entry_to_state_machine(self.state.commit_index)
                return success , self.state.current_term
            else:
                print("New entries recvd")
                
            # for a in entries:
            #     print(a.command)
            # print("done")
            # print("Last Applied", self.state.last_applied)
            # print("Commit Index", self.state.commit_index)
            # print("Hi111")
            # print("Previous Log Index: ",prev_log_index)
            # print("Logs: ",len(self.state.log))
            # print("Prev Log Term send by the leader: ",prev_log_term)
            # print("Current States Term at prev log index: ",{self.state.log[prev_log_index].term})

            # Check if log contains entry at prev_log_index whose term matches prev_log_term
            if (prev_log_index!=0 and prev_log_index <= len(self.state.log) and self.state.log[prev_log_index-1].term == prev_log_term) or (prev_log_index==0 and prev_log_term==0 and len(self.state.log)==0):
                success = True
                # print("here or not")

                
                # Insert entries not already in the log
                insert_position = prev_log_index + 1

                for entry in entries:

                    if insert_position < len(self.state.log):
                        # overwrite in the list here: Conflict resolution 
                        if self.state.log[insert_position].term != entry.term:
                            self.state.log = self.state.log[:insert_position]
                            self.state.log.append(entry)
                            self.state.append_to_logfile(entry.command)
                            
                    # append as list is finished        
                    else:
                        self.state.log.append(entry)
                        self.state.append_to_logfile(entry.command)
                    insert_position += 1
                    
                # if (len(entries)>0):
                    # print("Is the NO OP appended? ",len(self.state.log))

                # Update commit index
            if leader_commit > self.state.commit_index:
                # print("came here")
                self.state.commit_index = min(
                    leader_commit, len(self.state.log)) # chat gpt says -1
                # Apply newly committed entries to the state machine
                # print(f"Commit Index: {self.state.commit_index}")
                # print(f"Last Applied: {self.state.last_applied}")
                while (self.state.last_applied < self.state.commit_index):
                    # print("I am here")
                    self.state.apply_entry_to_state_machine(self.state.commit_index)
                        
                    

                self.state.persist_state()
            # print(f"hiasiahsiasiahsia {success}")
            if success:
                print(f"Previous Log Index matched and Node {self.state.node_id} accepted AppendEntries RPC from {leader_id}.")
                self.logger.info(
                    f"Node {self.state.node_id} accepted AppendEntries RPC from {leader_id}.")
            else:
                # print(f"xaxxzxz")
                
                # print("Previous Log Index did not match")
                self.logger.info(
                    f"Node {self.state.node_id} rejected AppendEntries RPC from {leader_id}.")
            # print(f"success: {success}")
            # print("-----------------------")
            return success , self.state.current_term
                # return {'term': self.state.current_term, 'success': success}
        except Exception as e:
            print(e)
        
    
        
    def on_receive_vote_request(self, term, candidate_id, last_log_index, last_log_term):
        vote_granted = False
        # with self.lock:
        #         Check if term is at least as large as the node's current term
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
            print(f"Vote granted for Node {candidate_id} in term {term}.")
            self.logger.info(
                f"Vote granted for Node {candidate_id} in term {term}.")
        else:
            print(f"Vote denied for Node {candidate_id} in term {term}.")
            self.logger.info(
                f"Vote denied for Node {candidate_id} in term {term}.")

        # Reset election timer here because a valid leader exists
        self.reset_election_timer()

        leader_lease_end = self.state.known_leader_lease_end
        return vote_granted , term, leader_lease_end
            # return {'term': self.state.current_term, 'voteGranted': vote_granted}
            
    def send_heartbeats(self):
        
        try:
            
        
        #  with self.lock:
            if not self.is_leader():
                print(f"{self.state.node_id} is not the leader.")
                return  # Only the leader sends heartbeats
            print(f"Leader {self.state.node_id} sending heartbeats.")
            self.logger.info(
                f"Leader {self.state.node_id} sending heartbeat & Renewing Lease")
            # Example heartbeat logic, assuming a method to send AppendEntries RPC
            if(not self.check_leader_lease_valid()):
                print(
                    f"Node {self.state.node_id} lease has expired")
                self.step_down()
                return

            votes = 1
            for peer_id in self.peers:
                if peer_id != self.state.node_id:
                    # Send a heartbeat (an AppendEntries RPC with no log entries) to each peer
                    self.reset_election_timer()
                    if(len(self.state.log)>=self.state.next_index[peer_id]):
                        entries = self.state.log[self.state.next_index[peer_id]-1:]
                        # print(f"{peer_id} : {entries[-1].command}")
                        # print(self.state.next_index[peer_id])
                    else:
                        entries=[]
                        # print(f"{peer_id}")
                    try:
                        response = self.send_append_entries(
                            peer_id, entries=entries, leader_commit=self.state.commit_index,lease_end=self.leader_lease_end)
                        if response is None:
                            continue
                    except Exception as e:
                        print(e,"\n") 
                        continue

                    if (response.success):
                        votes+=1
                        self.state.next_index[peer_id]=len(self.state.log)+1
                        self.state.match_index[peer_id]=len(self.state.log)
                        
                                
                    else:

                        self.state.next_index[peer_id]-=1
                        self.state.match_index[peer_id]-=1
            # self.entries=[]
            if votes > len(self.peers) // 2:
                self.state.commit_index = len(self.state.log)
                self.renew_leader_lease()

                # print(f"Commit Index: {self.state.commit_index}")
                # print(f"Last Applied: {self.state.last_applied}")
                while (self.state.last_applied < self.state.commit_index):
                    self.state.apply_entry_to_state_machine(self.state.commit_index) 
            else:
                self.logger.info(
                    f"Leader {self.state.node_id} lease renewal failed. Stepping Down")
                self.step_down()
            
            # else: # no majoriy received     
            #     if ( self.state.commit_index < len(self.state.log)): # new entry cant be commited
            #         while (self.state.commit_index!=len(self.state.log)):
            #               self.state.log.pop(-1)
                          
                    
                    
                
            
        except Exception as e:
            print("Error",e)

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
            logentry=LogEntry(term=self.state.current_term, command="No Op")
            
            self.state.add_entry(logentry,"No Op")
            self.leader_lease_end=time.time()+self.lease_duration
            # self.logger.info(
            #     f"Leader has acquired the Lease Token")
            
            def send_heartbeats_periodically():
                while self.is_leader():
                    self.send_heartbeats()
                    time.sleep(1)  # Sleep for 1 second before sending the next heartbeat

                # Start sending heartbeats periodically in a separate thread
            heartbeat_thread = threading.Thread(target=send_heartbeats_periodically)
            heartbeat_thread.start()


    def start_election(self):

        # with self.lock:

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

            # # Send RequestVote RPCs to all other nodes
            # for peer_id in self.peers:
            #     if peer_id != self.state.node_id:
            #         self.send_request_vote(peer_id)
            
            

            
            self.send_request_vote()
            

    def send_request_vote(self):
        # with self.lock:
            # self.logger.info(
            #     f"Node {self.state.node_id} sent a vote request to all peers.")

            last_log_index = len(self.state.log) - 1
            last_log_term = self.state.log[last_log_index].term if self.state.log else 0
            vote_count = 1  # Start with vote for self
            self.state.voted_for = self.state.node_id
            self.state.persist_state()
            latest_lease_end=0

            for peer_id, address in self.peers.items():
                if peer_id == self.state.node_id:
                    continue  # Skip self
                try:
                    with grpc.insecure_channel(address) as channel:
                        stub = raft_pb2_grpc.RaftServiceStub(channel)
                    
                        print(f"Sending vote request to {peer_id}.")
                    
                        response = stub.RequestVote(raft_pb2.RequestVoteArgs(
                            term=self.state.current_term,
                            candidate_id=self.state.node_id,
                            last_log_index=last_log_index,
                            last_log_term=last_log_term
                        ), timeout=0.05)
                        
                        if response.vote_granted:
                            print("vote received from:",peer_id)
                            vote_count += 1
                            latest_lease_end=max(response.leader_lease_end,latest_lease_end)


                        elif response.term > self.state.current_term:
                            print("vote denied from:",peer_id)
                            self.state.update_term(response.term)
                            break  # Break if we find a higher term
                        
                except grpc.RpcError as e:
                    print(f"Error occurred while sending RPC to Node {peer_id}.")
                    # print(f"Failed to send RequestVote to {peer_id}: {e}")
                    pass
            if vote_count > len(self.peers) // 2:
                time_to_wait = max(0, latest_lease_end)
                if self.election_timer.is_alive():
                    self.election_timer.cancel()
                print(f"Max Duration of leader lease remaining is {time_to_wait}")
                if time_to_wait > 0:
                    self.logger.info(f"New leader waiting for old leader lease to time out.")
                time.sleep(time_to_wait)    
                self.become_leader()
    def initialize_leader_state(self):
        # with self.lock:
            # Set next_index for each follower to the index just after the last one in the leader's log
            last_log_index = len(self.state.log)
            self.state.next_index = {
                peer_id: last_log_index + 1 for peer_id in self.peers}

            # Reset match_index for each follower to 0, since the leader doesn't know the highest log entry
            # replicated on the followers yet
            self.state.match_index = {peer_id: 0 for peer_id in self.peers}
            

    def send_append_entries(self, peer_id, entries, leader_commit,lease_end):
        
        #
        # check if there is any content to be sent from the handle_set from the leader to the followers
        # if there is then we need to send them in the heartbeat message to the followers
    
        peer_address = self.get_peer_address(peer_id)
        if not peer_address:
            print(f"No address found for peer {peer_id}.")
            return
       
        # Prepare the entries for gRPC call
        grpc_entries = [raft_pb2.LogEntry(
            command=e.command, term=e.term) for e in entries]
        # print("term:",self.state.current_term)
        # print("pref_log_index:",self.state.next_index[peer_id] - 1)
        # print("prev_log_term:",self.state.log[self.state.next_index[peer_id] -
        #                                  1].term if self.state.next_index[peer_id] > 1 else 0)
        
        # Create the gRPC request
        request = raft_pb2.AppendEntriesArgs(
            term=self.state.current_term,
            leader_id=self.state.node_id,
            prev_log_index=self.state.next_index[peer_id] - 1,
            prev_log_term=self.state.log[self.state.next_index[peer_id] -
                                         2].term if self.state.next_index[peer_id] > 1 else 0,
            entries=grpc_entries,
            leader_commit=leader_commit,
            leader_lease_duration= lease_end - time.time()
        )
        # if(len(request.entries)>0):

        #     print(request.prev_log_index)

        # Make the gRPC call
        with grpc.insecure_channel(peer_address) as channel:
            stub = raft_pb2_grpc.RaftServiceStub(channel)
            try:
                response = stub.AppendEntries(request,timeout=0.05)
                # print("here")
                if (response is not None): print(f"Received response from {peer_id}: {response.success}")
                if (response.term > self.state.current_term):
                    self.state.update_term(response.term)
                    self.step_down()

                return response
            except grpc.RpcError as e:
                print(f"Error occurred while sending RPC to Node {peer_id}.")
                # print(f"Failed to send AppendEntries to {peer_id}: {e}")
                pass


# This 
class RaftService(raft_pb2_grpc.RaftServiceServicer):

    def __init__(self, raft_server):
        self.raft_server = raft_server

    def ServeClient(self, request, context):
        
        # Handle client requests to the Raft cluster
        if request.request.startswith("GET"):
            key = request.request.split()[1]
            
            
            # if (key == 'leader' and self.raft_server.is_leader()):
            #     return raft_pb2.ServeClientReply(data="", success=True, leader_id=self.raft_server.leader_id)
            # elif (key == 'leader' and not self.raft_server.is_leader()):
            #     return raft_pb2.ServeClientReply(data="None", success=False, leader_id=self.raft_server.leader_id)    
            if (self.raft_server.is_leader()==False):
            
                if(self.raft_server.leader_id is None):
                    return raft_pb2.ServeClientReply(data="None", success=False, leader_id=self.raft_server.leader_id,statusCode=1)
                else:
                    return raft_pb2.ServeClientReply(data="", success=False, leader_id=self.raft_server.leader_id,statusCode=2)
                
            value, success = self.raft_server.handle_get(key,request.request)
            # print("val,success:",value,success)
            return raft_pb2.ServeClientReply(data=value, success=success, leader_id=self.raft_server.leader_id,statusCode=101)
        
        elif request.request.startswith("SET"):
            _, key, value = request.request.split()
            if (self.raft_server.is_leader()==False):
            
                if(self.raft_server.leader_id is None):
                    return raft_pb2.ServeClientReply(success=False, leader_id=self.raft_server.leader_id,statusCode=1)
                else:
                    return raft_pb2.ServeClientReply(success=False, leader_id=self.raft_server.leader_id,statusCode=2)
            success = self.raft_server.handle_set(key, value,request.request)
            return raft_pb2.ServeClientReply(success=success, leader_id=self.raft_server.leader_id,statusCode=101)

        else:
            print(f"Unknown request: {request.request}")
            return raft_pb2.ServeClientReply(success=False, leader_id=self.raft_server.leader_id,statusCode=3)

    def AppendEntries(self, request, context):
        # Implementation of the AppendEntries RPC for log replication
        
        
        success, term = self.raft_server.on_receive_append_entries(
            term=request.term,
            leader_id=request.leader_id,
            prev_log_index=request.prev_log_index,
            prev_log_term=request.prev_log_term,
            entries=request.entries,
            leader_commit=request.leader_commit,
            leader_lease_duration = request.leader_lease_duration
        )
        
        #else:  handle the case where the prev_log index does not match the follower's current log index
        # in such case we must ideally send failure and the leader should try again with prev log index called with prev_log index = prev_log_index - 1  
        # solution : call the self.raft_server.on_receive_append_entries with prev_log_index = prev_log_index - 1 in a while loop
        # solution : call the self.raft_server.on_receive_append_entries with prev_log_index = prev_log_index - 1 in a while loop
        
        
        return raft_pb2.AppendEntriesReply(term=term, success=success,statusCode=201)

    def RequestVote(self, request, context):
        # Implementation of the RequestVote RPC for leader election
        
        print(f"Received vote request from {request.candidate_id}.")
        print(f"Candidate term: {request.term}")
        
        vote_granted, term,leader_lease_end = self.raft_server.on_receive_vote_request(
            term=request.term,
            candidate_id=request.candidate_id,
            last_log_index=request.last_log_index,
            last_log_term=request.last_log_term
        )

        return raft_pb2.RequestVoteReply(term=term, vote_granted=vote_granted,statusCode=301,leader_lease_end=leader_lease_end)



def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    raftServer=RaftServer(NodeState(2,'logs_node_2'),{0:'localhost:50051',1:'localhost:50052',2:'localhost:50053',3:'localhost:50054',4:'localhost:50055'})
    raft_pb2_grpc.add_RaftServiceServicer_to_server(RaftService(raftServer), server)
    server.add_insecure_port('[::]:50053')
    server.start()
    server.wait_for_termination()


if __name__ == '__main__':
    serve()