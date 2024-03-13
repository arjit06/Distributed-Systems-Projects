import zmq
import json
import threading
from datetime import datetime
from uuid import uuid4
import time

max_clients=20



class GroupServer:
    def __init__(self, group_name, group_address,portnumber, server_address):
        self.group_name = group_name
        self.group_address = group_address
        self.server_address = server_address
        self.context = zmq.Context()
        self.users = {}
        self.messages = []
        self.lock = threading.Lock()
        self.available_ports = self.generate_ports(max_clients)
        self.req_socket = self.context.socket(zmq.REQ)
        self.req_socket.connect(f"tcp://{self.server_address}")
        self.user_socket = self.context.socket(zmq.REP)
        self.user_socket.bind(f"tcp://*:{portnumber}")
        self.max_clients=max_clients

    def generate_ports(self, num_ports):
        """Generate available ports for new user sockets."""
        base_port = int(self.group_address.split(':')[1])
        return [f"{self.group_address.split(':')[0]}:{base_port + i + 1}" for i in range(num_ports)]
    
    def register_with_message_server(self):
        self.req_socket.send_json(
            {"action": "register", "group_name": self.group_name, "address": self.group_address})
        message = self.req_socket.recv_json()
        status = message['status']
        print(f"Server response: {message}")
        if (status[0] == 'F'):
            return False
        else:
            return True
    def accept_user(self):
        """Accept a user and assign a port for communication."""
        if not self.available_ports:
            return None, None
        with self.lock:
            if not self.available_ports:
                return None, None
            user_address = self.available_ports.pop(0)
            user_address_port_no=user_address.split(':')[1]
        user_socket = self.context.socket(zmq.REP)
        user_socket.bind(f"tcp://*:{user_address_port_no}")
        return user_socket, user_address
    

    def handle_user(self):
        # print("Thread running")
        while True:
            message = self.user_socket.recv_json()
            action = message['action']
            if action == 'join':
                status,user_socket,user_address=self.join_group(message)
                if(status):
                    threading.Thread(target=self.handle_user_multiple, args=(user_socket, user_address), daemon=True).start()
                

                    



                
    def handle_user_multiple(self,user_socket,user_address):
        while True:
            message = user_socket.recv_json()
            action = message['action']
            if action == 'leave':
                self.leave_group(message,user_socket)
                break
            elif action == 'send_message':
                self.send_message(message,user_socket)
            elif action == 'get_message':
                self.receive_messages(message,user_socket)
        user_socket.close()
        with self.lock:
            self.available_ports.append(user_address)  # Free up the port for reuse

    def join_group(self, message):
        # print("Joiningnnnnnnn")
        user_id = message['user_id']
        user_name = message['username']
        if(user_name in self.users.keys()):
            self.user_socket.send_json({"status": "FAILURE","message":"You are already a part of this group"})
            return False,None,None
        
        if(len(self.users)>=self.max_clients):
            self.user_socket.send_json({"status": "FAILURE","message":"Too many clients. Try later"})
            return False,None,None
        self.users[user_name] = user_id
        user_socket, user_address = self.accept_user()
        if(user_socket):
            self.user_socket.send_json({"status": "SUCCESS", "user_id": user_id, "user_address": user_address})
            print(f"{self.group_name} - JOIN REQUEST FROM {user_id}")
            return True,user_socket,user_address
        else:
            self.user_socket.send_json({"status": "FAILURE","message":"Too many clients. Try later"})
            return False,None,None

    def leave_group(self, message,user_socket):
        user_name = message['username']
        if user_name in self.users:
            user_id = self.users[user_name]
            del self.users[user_name]
            print(f"{self.group_name} - LEAVE REQUEST FROM {user_id}")
            user_socket.send_json(
                {"status": "SUCCESS", "groupName": self.group_name})
        else:
            user_socket.send_json(
                {"status": "FAILED", "groupName": self.group_name})

    def send_message(self, message,user_socket):
        timestamp = datetime.now().strftime("%H:%M:%S")
        if(message['user_name'] not in self.users.keys()):
            user_socket.send_json({"status": "FAILURE"})
        else:
            user_id = self.users[message['user_name']]
            self.messages.append(
            {"timestamp": timestamp, "user_name": message['user_name'], "message": message['message']})
        
            user_socket.send_json({"status": "SUCCESS"})

            print(f"{self.group_name} - MESSAGE SEND FROM {user_id}: {message['message']}")

    def receive_messages(self, message,user_socket):
        user_name=message['user_name']
        if(user_name not in self.users.keys()):
            user_socket.send_json({"status": "FAILURE","message":"You are not a part of this group"})
        else:
            user_id=self.users[user_name]
            requested_time = message.get('timestamp')
            filtered_messages = [msg for msg in self.messages if msg['timestamp']
                             >= requested_time] if requested_time else self.messages
            user_socket.send_json({"status":"SUCCESS" , "message":filtered_messages})
            print(f"{self.group_name} - MESSAGES REQUESTED BY {user_id}")

    def start(self):
        status = self.register_with_message_server()
        if (status):
            #self.handle_user()
            threading.Thread(target=self.handle_user, daemon=True).start()
        else:
            print("FAILURE: Message Server registration failed. Maybe try with another name")


if __name__ == "__main__":
    # server1=GroupServer("Group1", "127.0.0.1:6000", "127.0.0.1:5555")
    # server1.start()
    # server2=GroupServer("Group2", "127.0.0.1:6001", "127.0.0.1:5555")
    # server2.start()
    # server3=GroupServer("Group3", "127.0.0.1:6002", "127.0.0.1:5555")
    # server3.start()
    Group_IP=input("Enter Group IP: ")
    Server_IP=input("Enter server IP: ")
    group_servers = [
        GroupServer("Group1", f"{Group_IP}:6000","6000", f"{Server_IP}:5555"),
        GroupServer("Group2", f"{Group_IP}:7000","7000", f"{Server_IP}:5555"),
        GroupServer("Group3", f"{Group_IP}:8000","8000", f"{Server_IP}:5555"),
        GroupServer("Group4", f"{Group_IP}:9000","9000", f"{Server_IP}:5555")
    ]

    for server in group_servers:
        server.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
