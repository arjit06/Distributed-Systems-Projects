import grpc
import random
import numpy as np
from concurrent import futures
import mapreduce_pb2
import mapreduce_pb2_grpc
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
import logging




def start_mapper_processes(num_mappers):
    mapper_processes = []
    for i in range(num_mappers):
        # Spawning each mapper process
        port = 50051 + i  # Ensure each mapper listens on a unique port
        mapper = subprocess.Popen(['python3', 'mapper.py', str(port)])
        mapper_processes.append(mapper)
    return mapper_processes

def start_reducer_processes(num_reducers):
    reducer_processes = []
    for i in range(num_reducers):
        # Spawning each reducer process
        port = 50100 + i  # Ensure each reducer listens on a unique port
        reducer = subprocess.Popen(['python', 'reducer.py', str(port), str(num_reducers)])
        reducer_processes.append(reducer)
    return reducer_processes

# New function to create or recreate the directory structure
def setup_directories(base_path, num_mappers, num_reducers):
    # Check if the base directory exists. If yes, delete and recreate it.
    # if os.path.exists(base_path):
    #     shutil.rmtree(base_path)
    os.makedirs(base_path,exist_ok=True)

    # Create input directory
    input_path = os.path.join(base_path, 'Input')
    os.makedirs(input_path,exist_ok=True)

    # Create mappers directory
    mappers_path = os.path.join(base_path, 'Mappers')
    for m in range(num_mappers):
        mapper_path = os.path.join(mappers_path, f'M{m+1}')
        os.makedirs(mapper_path,exist_ok=True)
        for r in range(num_reducers):
            partition_file = os.path.join(mapper_path, f'partition_{r+1}.txt')
            with open(partition_file, 'w') as f:
                f.write('')  # Create empty partition files

    # Create reducers directory
    reducers_path = os.path.join(base_path, 'Reducers')
    os.makedirs(reducers_path,exist_ok=True)
    for r in range(num_reducers):
        reducer_file = os.path.join(reducers_path, f'R{r+1}.txt')
        with open(reducer_file, 'w') as f:
            f.write('')  # Create an empty reducer file

    # Create file for centroids
    centroids_file_path = os.path.join(base_path, 'centroids.txt')
    with open(centroids_file_path, 'w') as f:
        f.write('')  # Create an empty centroids file

    return input_path, centroids_file_path


# Function to load data from file
def load_data(file_path):
    with open(file_path, 'r') as f:
        return [np.array(list(map(float, line.strip().split(',')))) for line in f]


# Function to randomly initialize centroids
def initialize_centroids(data, k):
    return random.sample(data, k)

# Function to divide data among mappers
def divide_data(data, num_mappers):    
    ans = []
    # we need to divide the data into equal parts and return a list of list where each nested list
    # is the start and end index of a data chunk for a mapper
    
    chunk_size = len(data) // num_mappers
    ans = [[i*chunk_size, (i+1)*chunk_size] for i in range(num_mappers)]
    
    if len(data) % num_mappers != 0:
        ans[-1][1] = len(data)
    
    return ans
    

# Function to determine if centroids have converged
def has_converged(old_centroids, new_centroids, threshold=0.000001):
    old_centroids = np.array(old_centroids)
    new_centroids = np.array(new_centroids)
    distances = np.linalg.norm(old_centroids - new_centroids, axis=1)
    return np.all(distances < threshold)

# Function to save centroids to file
def save_centroids(centroids, file_path):
    with open(file_path, 'w') as f:
        for centroid in centroids:
            f.write(','.join(map(str, centroid)) + '\n')
def send_to_mapper(stub,mapper_id,_range,num_mappers,num_reducers,num_centroids,centroids_msg,iteration,mapper_stubs,logger,recursion_depth=0):
    try:
        if(recursion_depth>num_mappers):
            return "All Mappers seem to be down. Come back later"
        logger.info(f"Request sent to mapper {mapper_id}")
        response = stub.StartMapTask(
                mapreduce_pb2.MapTaskRequest(start=_range[0], end=_range[1], M=num_mappers, R=num_reducers, K=num_centroids, centroids=centroids_msg,iteration_num=iteration),timeout=0.2)
        if response.status == "SUCCESS":
            print(f"SUCCESS:Response received from Mapper {mapper_id}")
            logger.info(f"SUCCESS:Response received from Mapper {mapper_id}")
            return "SUCCESS"
        else:
            print(f"FAILURE:Response Failed from Mapper {mapper_id}")
            logger.info(f"FAILURE:Response Failed from Mapper {mapper_id}")
            print(response)
            new_stub=stub
            while(stub==new_stub):
                new_stub=random.sample(mapper_stubs,1)[0]
                new_mapper_id=mapper_stubs.index(new_stub)
            response=send_to_mapper(new_stub,new_mapper_id+1,_range,num_mappers,num_reducers,num_centroids,centroids_msg,iteration,mapper_stubs,logger,recursion_depth+1)
        return response
    except grpc._channel._InactiveRpcError:
        print(f"FAILURE:Response Failed from Mapper {mapper_id}")
        logger.info(f"FAILURE:Response Failed from Mapper {mapper_id}")
        new_stub=stub
        while(stub==new_stub):
            new_stub=random.sample(mapper_stubs,1)[0]
            new_mapper_id=mapper_stubs.index(new_stub)

        response=send_to_mapper(new_stub,new_mapper_id+1,_range,num_mappers,num_reducers,num_centroids,centroids_msg,iteration,mapper_stubs,logger,recursion_depth+1)
        return response
    

def send_to_reducer(stub,reducer_id,num_mappers,num_reducers,num_centroids,centroids_msg,iteration,reducer_stubs,partition_id,logger,recursion_depth=0):
    try:
        if(recursion_depth>num_reducers):
            return "All Reducers seem to be down. Come back later"
        logger.info(f"Request sent to reducer {reducer_id}")
        response = stub.StartReduceTask(
                mapreduce_pb2.ReduceTaskRequest(M=num_mappers, R=num_reducers, K=num_centroids,iteration_num=iteration,partition_id=partition_id),timeout=0.8)
        if response.status == "SUCCESS":
            print(f"SUCCESS:Response received from Reducer {reducer_id} for partition {partition_id}")
            logger.info(f"SUCCESS:Response received from Reducer {reducer_id} for partition {partition_id}")
            return response
        else:
            print(f'FAILURE:Reduce task {reducer_id} failed on {partition_id}')
            logger.info(f'FAILURE:Reduce task {reducer_id} failed on {partition_id}')
            new_stub=stub
            while(stub==new_stub):
                new_stub=random.sample(reducer_stubs,1)[0]
                new_reducer_id=reducer_stubs.index(new_stub)
            response=send_to_reducer(new_stub,new_reducer_id+1,num_mappers,num_reducers,num_centroids,centroids_msg,iteration,reducer_stubs,partition_id,logger,recursion_depth+1)
    #     return response
    except grpc._channel._InactiveRpcError as e:
        print(f'FAILURE:Reduce task {reducer_id} failed on {partition_id}')
        logger.info(f'FAILURE:Reduce task {reducer_id} failed on {partition_id}')
        new_stub=stub
        while(stub==new_stub):
            new_stub=random.sample(reducer_stubs,1)[0]
            new_reducer_id=reducer_stubs.index(new_stub)
        response=send_to_reducer(new_stub,new_reducer_id+1,num_mappers,num_reducers,num_centroids,centroids_msg,iteration,reducer_stubs,partition_id,logger,recursion_depth+1)
        return response
def send_requests_to_mappers(mapper_stubs, list_of_ranges, num_mappers, num_reducers, num_centroids, centroids_msg, iteration, logger):
    with ThreadPoolExecutor(max_workers=num_mappers) as executor:
        futures = [
            executor.submit(send_to_mapper, stub, index+1, _range, num_mappers, num_reducers, num_centroids, centroids_msg, iteration, mapper_stubs, logger)
            for index, (stub, _range) in enumerate(zip(mapper_stubs, list_of_ranges))
        ]
        for future in futures:
            response = future.result()
            if response == 'All Mappers seem to be down. Come back later':
                logger.info("All Mappers seem to be down. Come back later")
                return "All Mappers seem to be down. Come back later"


def send_requests_to_reducers(reducer_stubs, num_mappers, num_reducers, num_centroids, centroids_msg, iteration, logger):
    with ThreadPoolExecutor(max_workers=num_reducers) as executor:
        futures = [
            executor.submit(send_to_reducer, stub, index+1, num_mappers, num_reducers, num_centroids, centroids_msg, iteration, reducer_stubs, index+1, logger)
            for index, stub in enumerate(reducer_stubs)
        ]
        updated_dict_centroids = []
        for future in futures:
            response = future.result()
            if response == 'All Reducers seem to be down. Come back later':
                logger.info("All Reducers seem to be down. Come back later")
                return
            updated_dict_centroids.extend([(centroid_update.key, [centroid_update.centroid.x, centroid_update.centroid.y]) for centroid_update in response.centroid_updates.updates])
        return updated_dict_centroids
def main(logger):
    
    print("Welcome to the K-Means MapReduce Master Program")
    num_mappers = int(sys.argv[1])
    num_reducers = int(sys.argv[2])
    num_centroids = int(sys.argv[3])
    max_iterations = int(sys.argv[4])
    
    base_path = "Data"
    
    # Create or recreate the directory structure
    input_path, centroids_file_path = setup_directories(base_path, num_mappers, num_reducers)

    # Load your data points from the input file
    data = load_data(os.path.join(input_path, "points2.txt"))
    if(len(data)<num_centroids):
        print("The number of centroids is greater than the number of data points. Please enter a valid number of centroids")
        return
    # Initialize centroids (could be randomly selected from the data points)
    centroids = initialize_centroids(data, k=num_centroids)
    
    #print the centroids that are randomaly selected
    print("Initial Centroids: ", centroids)
    logger.info(f"Initial Centroids: {centroids}")


    # Spawning mapper processes
    # mapper_processes = start_mapper_processes(num_mappers)
    mapper_stubs = [mapreduce_pb2_grpc.MapReduceStub(
        grpc.insecure_channel(f'localhost:{50051 + i}')) for i in range(num_mappers)]
    
    # # # Spawning reducer processes
    # reducer_processes = start_reducer_processes(num_reducers)
    reducer_stubs = [mapreduce_pb2_grpc.MapReduceStub(
        grpc.insecure_channel(f'localhost:{50100 + i}')) for i in range(num_reducers)]

    for iteration in range(max_iterations):
        
        previous_centroids = centroids
        
        list_of_ranges = divide_data(data, num_mappers=len(mapper_stubs))
        
        centroids_msg = mapreduce_pb2.Centroids(centroids=[
            mapreduce_pb2.Centroid(id=i, point=mapreduce_pb2.Point(x=centroid[0], y=centroid[1]))
            for i, centroid in enumerate(centroids)
        ])
        

        # Start map taskss
        response=send_requests_to_mappers(mapper_stubs, list_of_ranges, num_mappers, num_reducers, num_centroids, centroids_msg, iteration, logger)
        if(response=="All Mappers seem to be down. Come back later"):
            print("All Mappers seem to be down. Come back later")
            return
            


        updated_dict_centroids = send_requests_to_reducers(reducer_stubs, num_mappers, num_reducers, num_centroids, centroids_msg, iteration, logger)
        if(updated_dict_centroids == None):
            print("All Reducers seem to be done. Pls Come back later.")
            return
            
        
        centroids = [centroid[1] for centroid in sorted(updated_dict_centroids, key=lambda x: x[0])]
        
        print(f"Iteration: {iteration+1} , Updated Centroids: {centroids}")
        logger.info(f"Iteration: {iteration+1} , Updated Centroids: {centroids}")

        # Check for convergence
        # if has_converged(previous_centroids, centroids):
        #     print("Convergence reached after {} iterations.".format(iteration + 1))
        #     logger.info("Convergence reached after {} iterations.".format(iteration + 1))
        #     break

    # Save the final centroids to a file
    save_centroids(centroids, centroids_file_path)
    print("K-Means clustering completed. Centroids saved to", centroids_file_path)
    logger.info("KMeans Clustering completed. Centroids have been saved")

if __name__ == '__main__':
    logger=logging.getLogger()
    file_handler = logging.FileHandler(os.path.join(
            'Data', f'dump.txt') , mode='w')
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)
    main(logger)