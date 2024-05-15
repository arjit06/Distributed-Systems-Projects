import grpc
import raft_pb2
import raft_pb2_grpc
import time

class RaftClient:
    def __init__(self, servers):
        # servers is a dictionary mapping server IDs to their gRPC addresses
        self.servers = servers
        self.leader_id = None

    def send_request(self, command):

        
        
        
        # Edge case : only valid for the first election 
        # The client should be smart enough to identify that it should not send a request when there is a election going on.
        
        try:
            if not self.leader_id or self.leader_id not in self.servers:
                # ret = self.find_leader()
                pass
            try:
                response = self.send_to_leader(command)
                
                if (response is None):
                    print("FAILURE: There is no leader Yet.Please wait for the election to complete.")
                    return None
                
                if response.success:
                    print("SUCCESS")
                    return response.data
                else:
                    # If not successful, try updating the leader ID and retry
                    
                    # try to identify the correct type of error using error codes. Modify the proto file responses accordingly.
                    # example : [Read]incorrect key access (key does not exist)
                    # example : [Read]leader changes immeadiately after the request is sent
                    # example : [Write] write request errors : could not commit the write request because it could not get the majority.
                   
                    if response.statusCode==101:
                        if(command.split()[0]=="GET"): # if failure to execute on state machine and sent to the correct leader
                            print("FAILURE: Incorrect Key Access. Empty string returned")
                        else:
                            print("FAILURE: Could not get majority. Could not commit the write request.")
                        return
                    else:
                        print("FAILURE: Failed to execute command on leader.")
                        self.leader_id = response.leader_id
                    # return self.send_request(command)
                
            except Exception as e:
                print(f"FAILURE: Error sending request to leader: {e}")
                self.leader_id = None  # Reset leader ID if communication fails
                return None
            
        except:
            print("FAILURE: The Election is currently going on. Kindly retry after some time.")
            return None
        

    def find_leader(self):
        
        for server_id, address in self.servers.items():
            try:
                with grpc.insecure_channel(address) as channel:
                    stub = raft_pb2_grpc.RaftServiceStub(channel)
                    response = stub.ServeClient(raft_pb2.ServeClientArgs(request="GET leader"))
                    # print(response)
                    if (response.data == "None"):
                        return -1 

                        
                    else:
                        self.leader_id = response.leader_id
                        return self.leader_id
            
                    
            except Exception as e:
                print(f"FAILURE: Error finding leader on server {server_id}: {e}")
                continue
        raise Exception("FAILURE: Failed to find the leader in the cluster.")

    def send_to_leader(self, command):
        
        #ret = self.find_leader()    

        # if (ret == -1):
        # print("here1")
        #     return None
        if(self.leader_id):
            address=self.servers[self.leader_id]
            # print("Sending request to leader: ", self.leader_id, " at address: ", address)
            try:
                # print("before before here")
                with grpc.insecure_channel(address) as channel:
                    # print("before here")
                    stub = raft_pb2_grpc.RaftServiceStub(channel)
                    # print("here")
                    response=stub.ServeClient(raft_pb2.ServeClientArgs(request=command,timeout=0.05))
                    # print("here 2")
                    # print(response.leader_id,response.success,response.statusCode)
                    if(response.leader_id is None):
                        return None
                    elif(response.success==False):
                        self.leader_id = response.leader_id
                        return self.send_to_leader(command)    
                    return response
                
            except Exception as e:
                
                    # print("the leader is dead. RIP")
                    self.leader_id=None
                    # continue
                    return self.send_to_leader(command)
                    

                    

        else:
            for server_id, address in self.servers.items():
                try:
                    with grpc.insecure_channel(address) as channel:
                        stub = raft_pb2_grpc.RaftServiceStub(channel)
                        response = stub.ServeClient(raft_pb2.ServeClientArgs(request=command))
                        # print(response.leader_id,response.success,response.statusCode)
                        if (response.leader_id is None or response.statusCode == 1):
                            return None
                        
                        

                        elif (response.success == False):
                            
                            self.leader_id = response.leader_id
                            #return self.send_to_leader(command)
                            break
                        self.leader_id=response.leader_id
                        return response

                except Exception as e:
                    # print(f"Error sending request to leader: {e}")
                    # print("the leader is dead. RIP")
                    self.leader_id=None
                    continue 
                
                    # self.leader_id = None  # Reset leader ID if communication fails
                    # return None
                    
            try:
                address=self.servers[self.leader_id]
                with grpc.insecure_channel(address) as channel:
                    stub = raft_pb2_grpc.RaftServiceStub(channel)
                    response = stub.ServeClient(raft_pb2.ServeClientArgs(request=command))
                    return response
            except: # nothing has started yet 
                  return None 
        # if self.leader_id and self.leader_id in self.servers:
        #     address = self.servers[self.leader_id]
            

# Example usage
if __name__ == "__main__":
    servers = {0:'localhost:50051',1:'localhost:50052',2:'localhost:50053',3:'localhost:50054',4:'localhost:50055'}

    client = RaftClient(servers)
    
    print("Hello this is client!")
    print("----------------------")
    print("To exit write the command exit")
    print("----------------------")
    while True:
        print("----------------------")
        print("Enter the command to be executed:")
        print("----------------------")
        print()
        inp = input()
        out=client.send_request(inp)
        if out is not None:
            print(out)
        else:
            pass

        if (inp == "exit"):
            break

        