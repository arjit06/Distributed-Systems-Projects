import zmq
import json
import uuid
import os
from datetime import datetime
import time


class UserClient:
    def __init__(self, server_address,user_name):
        self.server_address = server_address
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(f"tcp://{self.server_address}")
        self.group_socket = None
        self.groups={}
        self.uuid=str(uuid.uuid1())

    def get_group_list(self):
        self.socket.send_json({"action": "get_groups","user_id":self.uuid})
        message = self.socket.recv_json()
        for name,ip in message.items():
            print(f"Name {name}: ip {ip} ")
        #print(f"Available groups: {message}")
        return message



    def connect_to_group(self, group_address):
        self.group_socket = self.context.socket(zmq.REQ)
        self.group_socket.connect(f"tcp://{group_address}")
        

    def join_group(self,user_name,group_name):

        self.group_socket.send_json({"action": "join", "user_id": self.uuid, "username": user_name})
        response = self.group_socket.recv_json()
        if(response.get('status')=='FAILURE'):
            print(response.get('message'))
            return None
        user_address=response.get('user_address')
        print(f"Join group response: {response['status']}")
        if(user_address==None):
            # print("Please try again\n")
            return None
        group_socket=self.context.socket(zmq.REQ)
        group_socket.connect(f"tcp://{user_address}")
        self.groups[group_name]=group_socket

        return user_address
    
    def leave_group(self, user_name,group_name):
        group_socket=self.groups[group_name]

        # unique_id = str(uuid.uuid1())
        group_socket.send_json({"action": "leave", "username": user_name,"user_id":self.uuid})
        response = group_socket.recv_json()
        print(f"Leave group response: {response['status']}")
        if(response['status']=='FAILED'):
            print("Leave group failed. Please try again.")
            return None
        del self.groups[group_name]
        return response
    

    def send_message(self, user_name,group_name, message):
        group_socket=self.groups[group_name]

        group_socket.send_json({"action": "send_message", "user_name": user_name, "message": message,"user_id":self.uuid})
        response = group_socket.recv_json()
        print(f"Send message response: {response['status']}")

    def get_messages(self, user_name,group_name, timestamp=None):
        group_socket=self.groups[group_name]

        request_data = {"action": "get_message", "user_name": user_name,"user_id":self.uuid}
        if timestamp:
            request_data['timestamp'] = timestamp
        group_socket.send_json(request_data)
        messages = group_socket.recv_json()
        status = messages.get('status')
        if(status=='FAILURE'):
            print(messages['message'])
        else:
            print(f"Received messages: ")
            for message in messages['message']:
                print(f"{message['timestamp']} - {message['user_name']}: {message['message']}")

if __name__ == "__main__":

    user_name=input("Enter user name:   ")
    Server_IP=input("Enter server IP:   ")
    user_client = UserClient(f"{Server_IP}:5555",user_name=user_name)
    print(f"Welcome {user_name}. Your uuid has been assigned\n")
    print("\n")
    groups={}
    while(True):
        print("Enter 1 to get group list")
        print("Enter 2 to join group")
        print("Enter 3 to leave group")
        print("Enter 4 to send message")
        print("Enter 5 to get messages")
        print("Enter 6 to exit")
        print("\n\n")
        choice=int(input("Enter your choice:  "))

        if(choice==1):
            groups=user_client.get_group_list()
        

        elif(choice==2):
            
            group_name=input("Enter group name:  ")
            if(not groups):
                print("Please try again.You need the group addresses first\n")
                continue
            elif(group_name not in groups.keys()):
                print("Please try again. No such group exists\n")
                continue
            
            user_client.connect_to_group(groups[group_name])
            user_address=user_client.join_group(user_name,group_name)
            if(user_address==None):
                print("Please try again.\n")
                continue
            #user_client.connect_to_group(user_address)
        # elif(user_client.group_socket==None):
        #     print("You are not connected to any group.\n Please connect and join.\n")
        elif(choice==3):
            group_name=input("Enter group name:  ")
            if(group_name not in user_client.groups.keys()):
                print("You are not part of this group.\n")
                continue
            user_client.leave_group(user_name,group_name)
        elif(choice==4):
            group_name=input("Enter group name:  ")
            if(group_name not in user_client.groups.keys()):
                print("You are not part of this group.\n")
                continue
            message=input("Enter message:  ")
            user_client.send_message(user_name,group_name,message)
        elif(choice==5):
            group_name=input("Enter group name:  ")
            if(group_name not in user_client.groups.keys()):
                print("You are not part of this group.\n")
                continue
            c=input("Do you want a time stamp (Y/N):  ")
            if(c.lower()=='y'):
                timestamp = input("Enter timestamp (HH:MM:SS):  ")
                user_client.get_messages(user_name,group_name, timestamp)
            else:
                user_client.get_messages(user_name,group_name)
        elif(choice==6):
            if(len(user_client.groups)>0):
                print("You must leave all groups first\n")
                continue
            break

    
    # user_client.send_message(user_info['user_id'], "Hello, this is User1!")
    # user_client.get_messages(user_info['user_id'])

