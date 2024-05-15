import grpc
import numpy as np
import os
import json
import mapreduce_pb2
import mapreduce_pb2_grpc
import sys
from concurrent import futures


class ReducerServicer(mapreduce_pb2_grpc.MapReduceServicer):
    def __init__(self, port):
        self.port = port
        self.reducer_id = port - 50100 + 1
        self.key_value_pairs = []
        self.final_data = []
        self.iteration_num=-1
        self.mode='w'
        self.iteration_set=set()

    def StartReduceTask(self, request, context):
        try:
            self.M = request.M
            self.R = request.R
            self.K=request.K
            self.key_value_pairs=[]
            if(request.iteration_num>self.iteration_num):
                self.iteration_num=request.iteration_num
                self.mode='w'
                self.iteation_set=set()
            else:
                self.mode='a'
            self.iteation_set.add(request.partition_id)
            mapper_stubs = [mapreduce_pb2_grpc.MapReduceStub(
                grpc.insecure_channel(f'localhost:{50051 + i}')) for i in range(self.M)]
            # prepare the fetchDataFromMapper Request 
            request = mapreduce_pb2.FetchDataFromMapperRequest(reducer_id = request.partition_id)
            for stub in mapper_stubs:
                try:
                    response = stub.FetchDataFromMapper(request,timeout=0.5)
                    self.key_value_pairs.extend(response.data)
                except grpc._channel._InactiveRpcError:

                    pass
            self.final_data=[(key_value_pair.key,[key_value_pair.value.x,key_value_pair.value.y]) for key_value_pair in self.key_value_pairs]
            self.final_data=self.shuffle_and_sort()
            
            reduced_data = self.reduce()
            self.write_output(reduced_data)
            # prepare the ReduceTaskResponse
            centroid_updates = mapreduce_pb2.CentroidUpdates()
            for key, centroid in reduced_data.items():
                centroid_update = centroid_updates.updates.add()
                centroid_update.key = key
                centroid_update.centroid.x = centroid[0]
                centroid_update.centroid.y = centroid[1]
            response = mapreduce_pb2.ReduceTaskResponse(
                status="SUCCESS",
                centroid_updates=centroid_updates
            )
            return response
        except Exception as e:
            return mapreduce_pb2.ReduceTaskResponse(status=f"FAILED: Exception: {str(e)}",centroid_updates=None)
        
    def shuffle_and_sort(self):
        def first_element(t):
            return t[0]
        
        sorted_data = sorted(self.final_data, key=first_element)
        return sorted_data
    
    def reduce(self):
        grouped_data = {}
        for key, value in self.final_data:
            if key not in grouped_data:
                grouped_data[key] = []
            grouped_data[key].append(value)
        
        reduced_data = {}
        for key, points in grouped_data.items():
            points_np = np.array(points)
            centroid = np.mean(points_np, axis=0)
            reduced_data[key] = centroid.tolist()
        return reduced_data
    
    def write_output(self, reduced_data):
        output_file = f'Data/Reducers/R{self.reducer_id}.txt'
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, self.mode) as f:
            for key, centroid in reduced_data.items():
                f.write(json.dumps({"key": key, "centroid": centroid}) + '\n')


if __name__ == "__main__":
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    port = int(sys.argv[1])
    mapreduce_pb2_grpc.add_MapReduceServicer_to_server(
        ReducerServicer(port), server)
    server.add_insecure_port(f'localhost:{port}')
    server.start()
    server.wait_for_termination()
