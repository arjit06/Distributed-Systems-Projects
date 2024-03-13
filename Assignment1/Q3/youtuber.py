import pika
import json
import sys

class Youtuber:
    def __init__(self):
        # self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        credentials = pika.PlainCredentials('arjit', 'arjit')
        parameters = pika.ConnectionParameters(host='34.131.83.62', #market ip
                                            port=5672,  # Default RabbitMQ port
                                            virtual_host='/',
                                            credentials=credentials)
        self.connection = pika.BlockingConnection(parameters)

        self.channel = self.connection.channel()
        self.channel.exchange_declare(exchange='youtube_exchange', exchange_type='direct',durable=True)

    def publishVideo(self, youtuber, videoName):
        message = {'youtuber': youtuber, 'video': videoName}
        self.channel.basic_publish(exchange='youtube_exchange', routing_key='video.upload', body=json.dumps(message),properties=pika.BasicProperties(delivery_mode=2))
        print("SUCCESS")

if __name__ == "__main__":
    youtuber = Youtuber()
    youtuber.publishVideo(sys.argv[1], ' '.join(sys.argv[2:]))
