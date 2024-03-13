# DSCD-Assigments

## Assignment 1
This assignment has three parts:-<br>
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
The YouTube-like application built with RabbitMQ consists of three main components: YouTuber, User, and YouTubeServer. YouTubers publish videos, Users subscribe/unsubscribe to YouTubers and receive notifications, while YouTubeServer manages requests and notifications. YoutubeServer.py handles user login, subscription, and video upload requests, notifying users on new uploads. Youtuber.py publishes videos to the server, and User.py manages subscriptions and receives notifications. The flow involves starting YouTubeServer.py, running Youtuber.py and User.py simultaneously, with users receiving real-time notifications on subscribed YouTuber uploads. Communication occurs solely via RabbitMQ message queues. <br><br><br><br>
