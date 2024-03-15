import grpc
import generate_pb2
import generate_pb2_grpc
from concurrent import futures
from google.protobuf.empty_pb2 import Empty

def print_menu():
    print("\n===== Buyer Menu =====")
    print("1. Search for items")
    print("2. Buy an item")
    print("3. Add an item to wishlist")
    print("4. Rate an item")
    print("5. Exit")
    print("======================")

def search_item(stub):
    item_name = input("Enter item name (leave blank for all items): ")
    category = input("Enter item category (ELECTRONICS, FASHION, OTHERS, ANY): ").upper()
    
    # print(f"Market prints: Search request for Item name: {item_name if item_name else '<empty>'}, Category: {category}.")
    
    response = stub.SearchItem(generate_pb2.SearchItemRequest(item_name=item_name, category=category))
    
    
    if (len(response.items) == 0):
        print("No items found.")
    
    for item in response.items:
        print(f"\nItem ID: {item.item_id}, Price: ${item.price}, Name: {item.name}, Category: {item.category},\nDescription: {item.description}.\nQuantity Remaining: {item.quantity}\nRating: {item.rating} / 5  |  Seller: {item.seller_address}\n")

def buy_item(stub):
    item_id = int(input("Enter item ID to buy: "))
    quantity = int(input("Enter quantity to purchase: "))
    buyer_address = input("Enter your notification server address (ip:port): ")
    
    response = stub.BuyItem(generate_pb2.BuyItemRequest(item_id=item_id, quantity=quantity, buyer_address=buyer_address))
    
    # print(f"Market prints: Buy request {quantity}[quantity] of item {item_id}[item id], from {buyer_address}[buyer address]")
    
    if (response.status):
        print("Purchase Unsuccessful.")
    else:
        print("Purchase Successful.")

def add_to_wishlist(stub):
    item_id = int(input("Enter item ID to add to wishlist: "))
    buyer_address = input("Enter your Notification server address (ip:port): ")
    
    response = stub.AddToWishList(generate_pb2.AddToWishListRequest(item_id=item_id, buyer_address=buyer_address))
    
    # print(f"Market prints: Wishlist request of item {item_id}[item id], from {buyer_address}")
    
    if (response.status):
        print("Add to Wishlist Unsuccessful.")
    else:
        print("Add to Wishlist Successful.")

def rate_item(stub):
    item_id = int(input("Enter item ID to rate: "))
    rating = int(input("Enter your rating (1 to 5): "))
    buyer_address = input("Enter your buyer server address (ip:port): ")
    
    response = stub.RateItem(generate_pb2.RateItemRequest(item_id=item_id, rating=rating, buyer_address=buyer_address))
    
    # print(f"Market prints: {buyer_address} rated item {item_id}[item id] with {rating} stars.")
    if (response.status):
        print("Rating Unsuccessful.")
    else:
        print("Rating Successful.")
        
        
def HandleBuyerNotifications(request) :
    
    seller_address = request.seller_address
    new_price = request.new_price
    new_quantity = request.new_quantity
    item_id = request.item_id
    
    print(f"Seller with address {seller_address} has updated the price of item with id {item_id} to ${new_price} and quantity to {new_quantity}")
    
    

def run():
    # with grpc.insecure_channel('34.131.59.13:50051') as channel:
    with grpc.insecure_channel('[::]:50051') as channel:
        stub = generate_pb2_grpc.MarketStub(channel)
        
        while True:
            print_menu()
            choice = input("Enter your choice: ")
            
            if choice == '1':
                search_item(stub)
            elif choice == '2':
                buy_item(stub)
            elif choice == '3':
                add_to_wishlist(stub)
            elif choice == '4':
                rate_item(stub)
            elif choice == '5':
                print("Exiting the buyer application.")
                break
            else:
                print("Invalid choice. Please try again.")
                
                                


class BuyerServicer(generate_pb2_grpc.BuyerServicer):
        
    def HandleBuyerNotifications(self,request,context):
        
        seller_address = request.seller_address
        new_price = request.new_price
        new_quantity = request.new_quantity
        item_id = request.item_id
        
        print(f"Seller with address {seller_address} has updated the price of item with id {item_id} to ${new_price} and quantity to {new_quantity}")


        return Empty()

if __name__ == '__main__':
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    generate_pb2_grpc.add_BuyerServicer_to_server(BuyerServicer(), server)
    server.add_insecure_port('[::]:50054')
    server.start()
    
    run()
