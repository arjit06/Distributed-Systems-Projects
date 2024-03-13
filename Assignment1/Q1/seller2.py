from concurrent import futures
import time

import grpc
import generate_pb2
import generate_pb2_grpc
import uuid

from google.protobuf.empty_pb2 import Empty

seller_address = ""


def print_menu():
    print("\n===== Seller Menu =====")
    print("1. Register as a seller")
    print("2. Add a product for sale")
    print("3. Update an existing product")
    print("4. Delete an existing product")
    print("5. View all products")
    print("6. Exit")
    print("========================")


def register_seller(stub):
    global seller_address
    seller_uuid = str(uuid.uuid1())
    # Here you would implement a way to dynamically assign ports or handle multiple clients.
    # seller_address = f'localhost:{input("Enter your notification server port: ")}'
    # input format : External IP + ServerPort
    seller_address = input("Enter IP:Port --> ")
    response = stub.RegisterSeller(generate_pb2.RegisterSellerRequest(
        uuid=seller_uuid, seller_address=seller_address))
    if response.status == generate_pb2.RegisterSellerResponse.SUCCESS:
        # print(f"Market printed: Seller join request from {seller_address}, uuid = {seller_uuid}")
        print("SUCCESS")
    else:
        print("FAIL")

    return seller_uuid


def add_product(stub, seller_uuid):

    name = input("Enter product name: ")
    category = input("Enter product category (ELECTRONICS, FASHION, OTHERS): ")
    description = input("Enter product description: ")
    quantity = int(input("Enter product quantity: "))
    price = float(input("Enter product price: "))

    category_request = generate_pb2.SellItemRequest(
        uuid=seller_uuid,
        name=name,
        description=description,
        quantity=quantity,
        price=price,
        is_others=True
    )

    if category == 'ELECTRONICS':
        category_request.is_electronics = True
    elif category == 'FASHION':
        category_request.is_fashion = True
    else:
        category_request.is_others = True

    response = stub.SellItem(category_request)

    if response.status == generate_pb2.SellItemResponse.SUCCESS:
        print(f"Item sold successfully, item ID: {response.item_id}")
    else:
        print("Failed to sell item.")


def update_product(stub, seller_uuid):
    item_id = int(input("Enter item ID to update: "))
    new_price = float(input("Enter new price: "))
    new_quantity = int(input("Enter new quantity: "))

    response = stub.UpdateItem(generate_pb2.UpdateItemRequest(
        uuid=seller_uuid, item_id=item_id, new_price=new_price, new_quantity=new_quantity
    ))

    if response.status == generate_pb2.UpdateItemResponse.SUCCESS:
        print("Item updated successfully.")
    else:
        print("Failed to update item.")


def delete_product(stub, seller_uuid):
    item_id = int(input("Enter item ID to delete: "))

    response = stub.DeleteItem(generate_pb2.DeleteItemRequest(
        uuid=seller_uuid, item_id=item_id
    ))

    if response.status == generate_pb2.DeleteItemResponse.SUCCESS:
        print("Item deleted successfully.")
    else:
        print("Failed to delete item.")


def view_products(stub, seller_uuid):

    response = stub.DisplaySellerItems(
        generate_pb2.DisplaySellerItemsRequest(uuid=seller_uuid))

    for item in response.items:
        print(f'''Item ID: {item.item_id}, Price: ${item.price}, Name: {item.name}, Category: {item.category},
Description: {item.description}.
Quantity Remaining: {item.quantity}
Seller: {seller_address}
Rating: {item.rating} / 5\n''')


def HandleSellerNotifications(request):

    item_id = request.item_id
    item_name = request.name
    quantity = request.quantity
    buyer_address = request.buyer_address

    print(
        f"Buyer with address {buyer_address} has bought quantity : {quantity} of {item_name} with id {item_id}")


def run():
    # Set up a connection to the server
    # with grpc.insecure_channel('34.131.59.13:50051') as channel: # Server IP
    with grpc.insecure_channel('[::]:50051') as channel:

        # Create a stub (client)
        stub = generate_pb2_grpc.MarketStub(channel)

        # Placeholder for seller's UUID
        seller_uuid = None

        while True:
            print_menu()
            choice = input("Enter your choice: ")

            if choice == '1':
                seller_uuid = register_seller(stub)

            elif choice == '2':
                if not seller_uuid:
                    print("You need to register first.")
                    continue
                add_product(stub, seller_uuid)

            elif choice == '3':
                if not seller_uuid:
                    print("You need to register first.")
                    continue
                update_product(stub, seller_uuid)

            elif choice == '4':
                if not seller_uuid:
                    print("You need to register first.")
                    continue
                delete_product(stub, seller_uuid)

            elif choice == '5':
                if not seller_uuid:
                    print("You need to register first.")
                    continue
                view_products(stub, seller_uuid)

            elif choice == '6':
                print("Exiting the seller application.")
                break

            else:
                print("Invalid choice. Please try again.")


class SellerServicer(generate_pb2_grpc.SellerServicer):

    def HandleSellerNotifications(self, request, context):

        item_id = request.item_id
        item_name = request.item_name
        quantity = request.quantity
        buyer_address = request.buyer_address

        print(
            f"Buyer with address {buyer_address} has bought quantity : {quantity} of {item_name} with id {item_id}")

        return Empty()


if __name__ == '__main__':

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    generate_pb2_grpc.add_SellerServicer_to_server(SellerServicer(), server)
    server.add_insecure_port('[::]:50055')
    server.start()

    run()
