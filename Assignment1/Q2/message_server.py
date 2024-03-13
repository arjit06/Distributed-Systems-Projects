import zmq
import json

class MessageServer:
    def __init__(self, port=5555):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind(f"tcp://*:{port}")
        self.groups = {}

    def start(self):
        while True:
            message = self.socket.recv_json()
            action = message['action']
            if action == 'register':
                self.register_group(message)
            elif action == 'get_groups':
                self.send_group_list(message)

    def register_group(self, message):
        group_name = message['group_name']
        group_address = message['address']
        print(f"JOIN REQUEST FROM {group_address}")
        if group_name in self.groups.keys():
            self.socket.send_json({"status": "FAILURE"})
        else:
            self.groups[group_name] = group_address
            self.socket.send_json({"status": "SUCCESS"})

    def send_group_list(self,message):
        print(f"GROUP LIST REQUEST FROM {message['user_id']}")
        self.socket.send_json(self.groups)

if __name__ == "__main__":
    server = MessageServer()
    server.start()
