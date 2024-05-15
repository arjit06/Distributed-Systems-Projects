# DSCD-Projects
All these assignments had to be hosted on Google Cloud to provide the simulation of a Distributed System. <br>
## Project 1
This project consists of  three parts:-<br>
<ul>
<li>Using gRPC to implement an online shopping platform</li>
<li>Using ZeroMQ to implement a group messaging application (think of groups in WhatsApp)</li>
<li>Using RabbitMQ to implement a YouTube-like application</li>
</ul>
<br>

### PART 1: <u>Using gRPC to implement an Online Shopping Platform</u>
The online shopping platform consists of three main components: Market (central platform), Seller (client), and Buyer (client), each residing on different virtual machine instances. Communication between these components occurs through gRPC using Protocol Buffers. Key functionalities include:
<ul>
<li>Sellers register with the Market, post items for sale, update item details, delete items, and view their uploaded items.</li>
<li>Buyers search for items, purchase them, add items to their wish list, and rate purchased or wish-listed items.</li>
<li>Notifications are sent to both buyers and sellers when relevant updates occur.</li>
<li>All interactions are authenticated using unique UUIDs and IP addresses of VM instances.</li>
</ul>
<br>

### PART 2: Using ZeroMQ to Low-Level Group Messaging Application
A ZeroMQ-based group messaging app includes a central message server, groups, and users. The server manages group lists and user interactions. Groups handle message storage and retrieval, while users join/leave groups and exchange messages. 
<ol>
<li>Message Server ↔ Group communication involves registration</li>
<li>User ↔ Message Server interactions include requesting group lists</li>
<li>User ↔ Group interactions encompass joining/leaving groups and message exchange.</li>
</ol>
<br>

### PART 3: Building a YouTube-like application with RabbitMQ
The YouTube-like application built with RabbitMQ consists of three main components: YouTuber, User, and YouTubeServer. YouTubers publish videos, Users subscribe/unsubscribe to YouTubers and receive notifications, while YouTubeServer manages requests and notifications. YoutubeServer.py handles user login, subscription, and video upload requests, notifying users on new uploads. Youtuber.py publishes videos to the server, and User.py manages subscriptions and receives notifications. The flow involves starting YouTubeServer.py, running Youtuber.py and User.py simultaneously, with users receiving real-time notifications on subscribed YouTuber uploads. Communication occurs solely via RabbitMQ message queues. <br><br><br>

## Project 2
### RAFT Application for Geo Distributed Databases with Leader Lease
This project implements a modified Raft consensus algorithm to manage a distributed key-value store with enhanced read performance. The modification introduces leader leases, allowing the leader node to serve read requests without quorum validation, significantly reducing latency in geo-distributed environments. The system supports leader election, log replication, and client interactions using gRPC for communication. Nodes handle persistent storage of logs and metadata in a structured directory format, ensuring fault tolerance and consistency. The implementation covers standard Raft functionalities, including periodic heartbeats, leader lease renewal, and follower synchronization. Comprehensive testing scenarios include leader election, fault tolerance, follower recovery, and leader lease timeouts to ensure robust operation and data integrity across the distributed cluster.<br><br><br> 

## Project 3
### K-Means Clustering with MapReduce Framework
This project implements the K-Means clustering algorithm using a custom MapReduce framework from scratch. The entire framework runs on a single machine with separate processes for the master, mappers, and reducers, all communicating via gRPC. The master process initializes the centroids, divides the dataset into chunks for the mappers, and orchestrates the MapReduce workflow. Mappers compute intermediate key-value pairs, partition them, and send them to reducers. Reducers then sort and group these pairs, updating the centroids. The process iterates until convergence or the maximum number of iterations is reached. The implementation handles fault tolerance by reassigning failed tasks and logs detailed execution steps for debugging. The final output is a set of centroids representing the clustered dataset.
