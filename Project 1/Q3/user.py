import pika
import json
import sys

class User:
    def __init__(self, username):
        self.username = username
        # self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        
        credentials = pika.PlainCredentials('arjit', 'arjit')
        parameters = pika.ConnectionParameters(host='34.131.83.62',  #market ip
                                            port=5672,  # Default RabbitMQ port
                                            virtual_host='/',
                                            credentials=credentials)
        self.connection = pika.BlockingConnection(parameters)
        
        self.channel = self.connection.channel()
        self.channel.exchange_declare(exchange='youtube_exchange', exchange_type='direct',durable=True)

    def updateSubscription(self, youtuber, subscribe):
        message = {'user': self.username, 'youtuber': youtuber, 'subscribe': subscribe}
        self.channel.basic_publish(exchange='youtube_exchange', routing_key='user.request', body=json.dumps(message), properties=pika.BasicProperties(delivery_mode=2))
        print("SUCCESS")

    def receiveNotifications(self):
        queue_name = f'{self.username}.queue'
        self.channel.queue_declare(queue=queue_name, durable=True)
        self.channel.queue_bind(exchange='youtube_exchange', queue=queue_name, routing_key=f'{self.username}.notification')
        


        def callback(ch, method, properties, body):
            notification = json.loads(body)
            print(f"New Notification: {notification['youtuber']} uploaded {notification['video']}")
            ch.basic_ack(delivery_tag = method.delivery_tag)

        self.channel.basic_consume(queue=queue_name, on_message_callback=callback)
        print('Waiting for notifications...')
        self.channel.start_consuming()

if __name__ == "__main__":
    username = sys.argv[1]
    user = User(username)
    
    if len(sys.argv) > 2:
        action = sys.argv[2]
        youtuber = sys.argv[3]
        subscribe = True if action == 's' else False
        user.updateSubscription(youtuber, subscribe)
    user.receiveNotifications()
