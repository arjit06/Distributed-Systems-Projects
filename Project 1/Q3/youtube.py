import pika
import json
import time
from multiprocessing import Process
import threading
class YouTubeServer:
    def __init__(self):
        self.users={}
        self.youtubers={}


    @staticmethod
    def consume_user_requests(self):
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        # connection = pika.BlockingConnection(pika.ConnectionParameters('34.131.109.178'))
        channel = connection.channel()
        channel.exchange_declare(exchange='youtube_exchange', exchange_type='direct',durable=True)

        result = channel.queue_declare(queue='',durable=True)
        queue_name = result.method.queue
        channel.queue_bind(exchange='youtube_exchange', queue=queue_name, routing_key='user.request')

        def callback(ch, method, properties, body):
            request = json.loads(body)
            if 'login' in request:
                print(f"{request['user']} logged in")
                if(request['user'] not in self.users.keys()):
                    self.users[request['user']]=[]
                    
            elif 'subscribe' in request:
                action = 'subscribed' if request['subscribe'] else 'unsubscribed'
                print(f"{request['user']} {action} to {request['youtuber']}")
                if(request['user'] not in self.users.keys()):
                    self.users[request['user']]=[]
                if(action=='subscribed'):
                    self.users[request['user']].append(request['youtuber'])
                else:
                    ind=self.users[request['user']].index(request['youtuber'])
                    self.users[request['user']].pop(ind)
            ch.basic_ack(delivery_tag = method.delivery_tag)

        channel.basic_consume(queue=queue_name, on_message_callback=callback)
        print('Waiting for user requests...')
        channel.start_consuming()

    @staticmethod
    def consume_youtuber_requests(self):
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        # connection = pika.BlockingConnection(pika.ConnectionParameters('34.131.83.62'))
        channel = connection.channel()
        channel.exchange_declare(exchange='youtube_exchange', exchange_type='direct',durable=True)

        result = channel.queue_declare(queue='',durable=True)
        queue_name = result.method.queue
        channel.queue_bind(exchange='youtube_exchange', queue=queue_name, routing_key='video.upload')

        def callback(ch, method, properties, body):
            request = json.loads(body)
            youtuber=request['youtuber']
            videoname=request['video']
            if youtuber not in self.youtubers.keys():
                self.youtubers[youtuber]=[]
            self.youtubers[request['youtuber']].append(videoname)
            print(f"{request['youtuber']} uploaded {request['video']}")
            
            youtuber=request['youtuber']
            videoname=request['video']
            self.notify_users(youtuber,videoname,channel)
            ch.basic_ack(delivery_tag = method.delivery_tag)

        channel.basic_consume(queue=queue_name, on_message_callback=callback)
        print('Waiting for youtuber requests...')
        channel.start_consuming()
    
    def notify_users(self,youtuber,videoName,channel):
        for user,youtubers in self.users.items():
            if youtuber in youtubers:
                # print(self.users)
                message = {'youtuber': youtuber, 'video': videoName}
                
                result = channel.queue_declare(queue=f'{user}.queue',durable=True)
                channel.basic_publish(exchange='youtube_exchange', routing_key=f'{user}.notification', body=json.dumps(message),properties=pika.BasicProperties(delivery_mode=2))
                
                
            
        
        
        
    

if __name__ == "__main__":
    server1=YouTubeServer()
    server2=YouTubeServer()
    
    # user_requests_process = Process(target=server1.consume_user_requests,args=(server1,))
    # youtuber_requests_process = Process(target=server2.consume_youtuber_requests, args=(server2,))
    user_requests_process=threading.Thread(target=server1.consume_user_requests,args=(server1,))
    youtuber_requests_process=threading.Thread(target=server1.consume_youtuber_requests,args=(server1,))
    user_requests_process.start()
    youtuber_requests_process.start()

    user_requests_process.join()
    youtuber_requests_process.join()
