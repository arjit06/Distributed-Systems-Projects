from concurrent import futures
import grpc
import generate_pb2
import generate_pb2_grpc

# Assuming we have a data store for items, sellers, and buyers
items_db = {}
sellers_db = {}
buyers_db = {}

class MarketServicer(generate_pb2_grpc.MarketServicer):

    def RegisterSeller(self, request, context):
        if request.uuid in sellers_db:
            return generate_pb2.RegisterSellerResponse(status=generate_pb2.RegisterSellerResponse.FAIL)
        sellers_db[request.uuid] = {'address': request.seller_address}
        
        print(f"Seller join request from {request.seller_address}, uuid = {request.uuid}")
        return generate_pb2.RegisterSellerResponse(status=generate_pb2.RegisterSellerResponse.SUCCESS)

    def SellItem(self, request, context):
        if request.is_electronics:
            category = "ELECTRONICS"
        elif request.is_fashion:
            category = "FASHION"
        else:
            category = "OTHERS"
            
        item_id = len(items_db) + 1  # Simple ID generation
        items_db[item_id] = {
            'name': request.name,
            'category': category,
            'description': request.description,
            'quantity': request.quantity,
            'price': request.price,
            'seller_uuid': request.uuid
        }
        
        print(f"Sell Item request from {sellers_db[request.uuid]['address']}")
        return generate_pb2.SellItemResponse(status=generate_pb2.SellItemResponse.SUCCESS, item_id=item_id)

    
    def UpdateItem(self, request, context):
        # Check if the item exists and if the seller UUID matches
        item_to_update = items_db.get(request.item_id)
        if item_to_update and item_to_update['seller_uuid'] == request.uuid:
            # Update the item details
            if request.new_price:
                item_to_update['price'] = request.new_price
            if request.new_quantity:
                item_to_update['quantity'] = request.new_quantity
            # Assuming we have other fields that can be updated, they would be handled here

            # Update the item in the database
            items_db[request.item_id] = item_to_update
            print(f"Update Item request from {sellers_db[request.uuid]['address']}")
            # Send notifications to interested buyers
            # This is a simplification. In practice, you'd have a more complex notification system.
            
            for buyer_address , wishlist in buyers_db.items():
                
                if request.item_id in wishlist['wishlist']:
                    
                    seller_addr = sellers_db[request.uuid]['address']
                    item_id = request.item_id
                    new_price = request.new_price
                    new_quantity = request.new_quantity
                    
                    self.NotifyClient(buyer_address, seller_addr, item_id, new_price, new_quantity)
                
            # Return a success response
            return generate_pb2.UpdateItemResponse(status=generate_pb2.UpdateItemResponse.SUCCESS)
        else:
            # Return a failure response if the item doesn't exist or if the seller UUID doesn't match
            return generate_pb2.UpdateItemResponse(status=generate_pb2.UpdateItemResponse.FAIL)

    def DeleteItem(self, request, context):
        
        # Check if the item exists
        if request.item_id not in items_db:
            # Item does not exist, so cannot be deleted
            return generate_pb2.DeleteItemResponse(status=generate_pb2.DeleteItemResponse.FAIL)

        # Fetch the item
        item_to_delete = items_db.get(request.item_id)

        # Verify that the UUID in the request matches the item's seller UUID
        if item_to_delete['seller_uuid'] != request.uuid:
            # UUID does not match; the requester is not the item's seller
            return generate_pb2.DeleteItemResponse(status=generate_pb2.DeleteItemResponse.FAIL)

        # Delete the item
        del items_db[request.item_id]
        
        print(f"Delete Item request from {sellers_db[request.uuid]['address']}")

        # Optionally, notify interested buyers that the item has been removed
        # This would require tracking which buyers are interested in which items,
        # possibly through a wish list feature or similar

        # Return a success response
        return generate_pb2.DeleteItemResponse(status=generate_pb2.DeleteItemResponse.SUCCESS)


    def DisplaySellerItems(self, request, context):
        # Initialize an empty list to hold the items belonging to the seller
        seller_items = []

        # Loop through all items in the database to find those that belong to the requesting seller
        for item_id, item_details in items_db.items():
            if item_details['seller_uuid'] == request.uuid:
                # Construct an item message for each item found
                
                item_message = generate_pb2.DisplaySellerItemsResponse.Item(
                    item_id=item_id,
                    name=item_details['name'],
                    category=item_details['category'],
                    description=item_details['description'],
                    quantity=item_details['quantity'],
                    price=item_details['price'],
                    rating=item_details.get('rating', 0)  # Assuming an optional rating field, defaulting to 0
                )
                
                # Add the item message to the list of seller items
                seller_items.append(item_message)
                print(f"Display Items request from {sellers_db[request.uuid]['address']}")
                 
                

        # Return all the seller's items in the response
        return generate_pb2.DisplaySellerItemsResponse(items=seller_items)


    # Implement buyer related methods
    def SearchItem(self, request, context):
        
        # Extract the search criteria from the request
        query = request.item_name.lower()  # Assuming case-insensitive search
        category = request.category.lower()

        # Initialize an empty list to hold the search results
        search_results = []

        # Loop through all items in the database to find matches
        for item_id, item_details in items_db.items():
            # Check if the item matches the search criteria
            name_match = query in item_details['name'].lower()
            category_match = category == "any" or category == item_details['category'].lower()

            if name_match and category_match:
                # Construct an item message for each matching item
                item_message = generate_pb2.SearchItemResponse.Item(
                    item_id=item_id,
                    name=item_details['name'],
                    category=item_details['category'],
                    description=item_details['description'],
                    quantity=item_details['quantity'],
                    price=item_details['price'],
                    rating=item_details.get('rating', 0),  # Assuming an optional rating field, defaulting to 0,
                    seller_address = sellers_db[items_db[item_id]['seller_uuid']]['address']
                )
                # Add the item message to the list of search results
                search_results.append(item_message)
                
                
        print(f"Search request for Item name: {query}, Category: {category}.")

        # Return the search results in the response
        return generate_pb2.SearchItemResponse(items=search_results)
    


    def BuyItem(self, request, context):
        # Check if the item exists
        if request.item_id not in items_db:
            # Item does not exist
            print(f"Item {request.item_id} does not exist")
            return generate_pb2.BuyItemResponse(status=generate_pb2.BuyItemResponse.FAIL)

        item = items_db[request.item_id]
        
        # Check if the requested quantity is available
        if item['quantity'] < request.quantity:
            # Not enough stock
            print(f"Not enough stock for item {request.item_id}")
            return generate_pb2.BuyItemResponse(status=generate_pb2.BuyItemResponse.FAIL)

        # Update the item's quantity
        item['quantity'] -= request.quantity
        items_db[request.item_id] = item

        # Optionally, send a notification to the seller about the sale
        # Assuming we have a method to send notifications
        
        self.NotifySeller(request.item_id, request.buyer_address)
        print(f"Buy request {request.quantity} of item {request.item_id}, from {request.buyer_address}")

        # Return a success response
        return generate_pb2.BuyItemResponse(status=generate_pb2.BuyItemResponse.SUCCESS)


    def AddToWishList(self, request, context):
        # Check if the item exists
        if request.item_id not in items_db:
            # Item does not exist
            return generate_pb2.AddToWishListResponse(status=generate_pb2.AddToWishListResponse.FAIL)

        # Assuming buyers_db is a dictionary storing buyer's wishlists
        # Key: buyer's UUID, Value: Set of item IDs
        buyer_address = request.buyer_address
        item_id = request.item_id

        # Check if the buyer exists in the buyers_db; if not, add them
        if buyer_address not in buyers_db:
            buyers_db[buyer_address] = {'wishlist': set()}

        # Add the item to the buyer's wishlist
        buyers_db[buyer_address]['wishlist'].add(item_id)
        
        print(f"Wishlist request of item {item_id} from {buyer_address}")

        # Return a success response
        return generate_pb2.AddToWishListResponse(status=generate_pb2.AddToWishListResponse.SUCCESS)

    def RateItem(self, request, context):
        # Check if the item exists
        if request.item_id not in items_db:
            # Item does not exist
            return generate_pb2.RateItemResponse(status=generate_pb2.RateItemResponse.FAIL)
        

        item = items_db[request.item_id]
        
        # Assuming each item has a 'ratings' list to store individual ratings
        # and a 'average_rating' field to store the calculated average rating.
        if 'ratings' not in item:
            item['ratings'] = []
            
        if 'buyer_address' not in item:
            item['buyer_address'] = request.buyer_address
        else:
            if item['buyer_address'] == request.buyer_address:
                print("Buyer Already Rated")
                return generate_pb2.RateItemResponse(status=generate_pb2.RateItemResponse.FAIL)
            else:
                item['buyer_address'] = request.buyer_address


        # Add the new rating to the item's ratings list
        item['ratings'].append(request.rating)

        # Calculate the new average rating
        average_rating = sum(item['ratings']) / len(item['ratings'])
        
        item['average_rating'] = average_rating

        item['buyer_address'] = request.buyer_address
        
        item['rating']=item['average_rating']

        # Update the item in the database
        items_db[request.item_id] = item

        # Optionally, notify the seller that their item has been rated
        # This would require additional logic to find the seller and send a notification

        # Return a success response
        print(f"{request.buyer_address} rated item {request.item_id} with {request.rating} stars.")
        return generate_pb2.RateItemResponse(status=generate_pb2.RateItemResponse.SUCCESS)


    def NotifyClient(self, buyer_address,seller_address , item_id , new_price, new_quantity):
        # Extract information from the request

        # Simulate sending the notification
        # In a real system, this might involve sending an email, SMS, or pushing a notification to a client app
        print(f"Notification sent to {buyer_address}")

        with grpc.insecure_channel(buyer_address) as channel:
        
            # Create a Buyer stub
            Buyer_Stub = generate_pb2_grpc.BuyerStub(channel)
            op = Buyer_Stub.HandleBuyerNotifications(generate_pb2.NotifyClientRequest(seller_address=seller_address,new_price = new_price, new_quantity = new_quantity,item_id = item_id))

    
    
    def NotifySeller(self, item_id, buyer_address):
        
        seller_address = sellers_db[items_db[item_id]['seller_uuid']]['address']
        item_name = items_db[item_id]['name']
        quantity = items_db[item_id]['quantity']
        
        print(f"Notification sent to {seller_address}")
        
        # Send a NotifcationRequest to Seller through Seller Stub
        
        with grpc.insecure_channel(seller_address) as channel:
        
            # Create a Seller stub
            Seller_Stub = generate_pb2_grpc.SellerStub(channel)
            op = Seller_Stub.HandleSellerNotifications(generate_pb2.NotifySellerRequest(buyer_address=buyer_address, item_id = item_id, item_name = item_name, quantity = quantity))

        

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    generate_pb2_grpc.add_MarketServicer_to_server(MarketServicer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()
