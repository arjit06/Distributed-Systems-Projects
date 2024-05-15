import os
import sys
import numpy as np
import json
import grpc
import mapreduce_pb2
import mapreduce_pb2_grpc
from contextlib import redirect_stdout, redirect_stderr

# import future
from concurrent import futures


class MapperServicer(mapreduce_pb2_grpc.MapReduceServicer):
    
    def __init__(self, port):
        self.port = port
        self.data_points = []
        self.centroids_dict = {}
        self.iteration_num=-1
        self.mode='w'
        
    def partition_data(self, mapped_data, num_reducers):
        """Partition mapped data into R partitions where R is the number of reducers."""
        partitions = {i: [] for i in range(num_reducers)}
        for key_value in mapped_data:
            key, value = key_value
            reducer_index = key % num_reducers  # Simple hash function for partitioning
            partitions[reducer_index].append(key_value)
        return partitions

    def load_data_points(self, start, end):
        """Load the designated range of data points from the shared file."""
        with open('Data/Input/convergence.txt', 'r') as f:
            lines = f.readlines()[start:end]
            self.data_points = [np.array(list(map(float, line.strip().split(',')))) for line in lines]

    def find_nearest_centroid(self, data_point):
        """Find the nearest centroid for a given data point."""
        distances = [np.linalg.norm(data_point - np.array([centroid['x'], centroid['y']])) for centroid in self.centroids_dict.values()]
        return np.argmin(distances)+1

    def map_data_points(self):
        """Map each data point to its nearest centroid."""
        mapped_data = [(self.find_nearest_centroid(data_point), data_point.tolist()) for data_point in self.data_points]
        return mapped_data

    def write_partitions_to_files(self, partitions):
        """Write each partition to a separate file, ensuring data is JSON-serializable."""
        mapper_id = self.port - 50051 + 1
        for reducer_index, partition_data in partitions.items():
            output_file_path = f'Data/Mappers/M{mapper_id}/partition_{reducer_index + 1}.txt'
            os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
            with open(output_file_path, self.mode) as f:
                for key, value in partition_data:
                    # Convert NumPy data types to native Python types for JSON serialization
                    key = int(key)  # Convert np.int64 to int if necessary
                    value = [float(x) for x in value]  # Convert elements of np.array to float
                    serializable_pair = {"key": key, "value": value}
                    f.write(json.dumps(serializable_pair) + '\n')
                    
    def StartMapTask(self, request, context):
        
        try:
            self.num_mappers = request.M  
            self.num_reducers = request.R 
            
            
            self.centroids_dict = {centroid.id: {'x': centroid.point.x, 'y': centroid.point.y} for centroid in request.centroids.centroids}
            
            self.load_data_points(request.start, request.end)
            mapped_data = self.map_data_points()
            
            # Partitioning mapped data
            num_reducers = request.R  # Assuming the number of reducers is passed in the request
            partitions = self.partition_data(mapped_data, num_reducers)
            if(request.iteration_num>self.iteration_num):
                self.mode='w'
                self.iteration_num=request.iteration_num
            else:
                self.mode='a'
            # Writing partitions to files
            self.write_partitions_to_files(partitions)  
            return mapreduce_pb2.MapTaskResponse(status="SUCCESS")
        except Exception as e:
            return mapreduce_pb2.MapTaskResponse(status=f"FAILED: Exception: {str(e)}")


    def FetchDataFromMapper(self, request, context):
        
        
        try:
            reducer_id = request.reducer_id
            response_data = []

            for mapper_id in range(1, self.num_mappers + 1):
                partition_file_path = f"Data/Mappers/M{mapper_id}/partition_{reducer_id}.txt"
                with open(partition_file_path, 'r') as file:
                    for line in file:
                        data = json.loads(line)
                        key = data["key"]
                        value = data["value"]
                        response_data.append(mapreduce_pb2.KeyValuePair(key=key, value=mapreduce_pb2.Point(x=value[0], y=value[1])))

            return mapreduce_pb2.FetchDataFromMapperResponse(status="SUCCESS", data=response_data)
        except Exception as e:
            return mapreduce_pb2.FetchDataFromMapperResponse(status=f"FAILED: Exception: {str(e)}")

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    port = int(sys.argv[1])
    
    mapreduce_pb2_grpc.add_MapReduceServicer_to_server(
        MapperServicer(port), server)

    server.add_insecure_port(f'localhost:{port}')
    server.start()
    server.wait_for_termination()


if __name__ == '__main__':
    serve()
