# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc

import mapreduce_pb2 as mapreduce__pb2


class MapReduceStub(object):
    """The MapReduce service definition.
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.StartMapTask = channel.unary_unary(
                '/kmeans.MapReduce/StartMapTask',
                request_serializer=mapreduce__pb2.MapTaskRequest.SerializeToString,
                response_deserializer=mapreduce__pb2.MapTaskResponse.FromString,
                )
        self.StartReduceTask = channel.unary_unary(
                '/kmeans.MapReduce/StartReduceTask',
                request_serializer=mapreduce__pb2.ReduceTaskRequest.SerializeToString,
                response_deserializer=mapreduce__pb2.ReduceTaskResponse.FromString,
                )
        self.FetchDataFromMapper = channel.unary_unary(
                '/kmeans.MapReduce/FetchDataFromMapper',
                request_serializer=mapreduce__pb2.FetchDataFromMapperRequest.SerializeToString,
                response_deserializer=mapreduce__pb2.FetchDataFromMapperResponse.FromString,
                )


class MapReduceServicer(object):
    """The MapReduce service definition.
    """

    def StartMapTask(self, request, context):
        """Method for the Master to start a map task on a Mapper.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def StartReduceTask(self, request, context):
        """Method for the Master to start a reduce task on a Reducer.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def FetchDataFromMapper(self, request, context):
        """Method for a Reducer to fetch data from a Mapper.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_MapReduceServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'StartMapTask': grpc.unary_unary_rpc_method_handler(
                    servicer.StartMapTask,
                    request_deserializer=mapreduce__pb2.MapTaskRequest.FromString,
                    response_serializer=mapreduce__pb2.MapTaskResponse.SerializeToString,
            ),
            'StartReduceTask': grpc.unary_unary_rpc_method_handler(
                    servicer.StartReduceTask,
                    request_deserializer=mapreduce__pb2.ReduceTaskRequest.FromString,
                    response_serializer=mapreduce__pb2.ReduceTaskResponse.SerializeToString,
            ),
            'FetchDataFromMapper': grpc.unary_unary_rpc_method_handler(
                    servicer.FetchDataFromMapper,
                    request_deserializer=mapreduce__pb2.FetchDataFromMapperRequest.FromString,
                    response_serializer=mapreduce__pb2.FetchDataFromMapperResponse.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'kmeans.MapReduce', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


 # This class is part of an EXPERIMENTAL API.
class MapReduce(object):
    """The MapReduce service definition.
    """

    @staticmethod
    def StartMapTask(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/kmeans.MapReduce/StartMapTask',
            mapreduce__pb2.MapTaskRequest.SerializeToString,
            mapreduce__pb2.MapTaskResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def StartReduceTask(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/kmeans.MapReduce/StartReduceTask',
            mapreduce__pb2.ReduceTaskRequest.SerializeToString,
            mapreduce__pb2.ReduceTaskResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def FetchDataFromMapper(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/kmeans.MapReduce/FetchDataFromMapper',
            mapreduce__pb2.FetchDataFromMapperRequest.SerializeToString,
            mapreduce__pb2.FetchDataFromMapperResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)


class ServeReducerStub(object):
    """Missing associated documentation comment in .proto file."""

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """


class ServeReducerServicer(object):
    """Missing associated documentation comment in .proto file."""


def add_ServeReducerServicer_to_server(servicer, server):
    rpc_method_handlers = {
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'kmeans.ServeReducer', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


 # This class is part of an EXPERIMENTAL API.
class ServeReducer(object):
    """Missing associated documentation comment in .proto file."""
