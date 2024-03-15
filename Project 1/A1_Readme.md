DSCD ASSIGNMENT - 1

Q1

Python Files submitted:

1) Seller.py

2) Seller2.py

3) Buyer.py

4) Buyer2.py

5) Market.py

6) Along with generate.proto 

Run the proto file using the following command 

**python3 -m grpc_tools.protoc -I protos --python_out=. --grpc_python_out=. protos/generate.proto**

Note : 

To run the files on the Google cloud each seller and buyer needs to manually hard code the value of the external IP and port of the market. Also we have taken the IP and port for the notifications server’s of client and buyer as input.

with grpc.insecure_channel('34.131.59.13:50051') as channel: # Server IP

Question 2

Run the files in the following order:

1)**message_server.py**: python3 message_server.py(on google cloud)

2)**group.py**: python3 group.py (on google cloud)

3)**user_1.py**: python user_1.py(local)

4)**user_3.py**: python user_2.py(local)

The group.py and the user_1.py(and user_3.py) both need the IP address of the server. Obtain that from the Google Cloud(external IP)

Assumptions:

1)user_1.py(user_3.py) needs to leave all groups before terminating itself, since we would want to deallocate all resources(for this user) on the group_server side.

2)Multiple users can connect to the same group at a point in time. Also a single user can make themselves a part of multiple groups. 

