
""" 
    (assistant_message, customer_reply, extracted_fields)
"""

conversation1 = [
    (
        "Hello! 👋 How can I help you with your taxi booking today?",
        "Hi, I need a taxi from Main Street to the airport at 6 am tomorrow.",
        {
            "pickup_location": "Main Street",
            "destination": "airport",
            "pickup_time": "6 am tomorrow"
        }
    ),
    (
        "How many passengers will be traveling?",
        "Just me.",
        {
            "passengers": 1
        }
    ),
    (
        "Perfect. Do you have any special requests for the ride?",
        "No, that’s fine.",
        {
            "special_requests": "N/A"
        }
    ),
    (
        "Thank you!\nPlease confirm:\n Pickup: Main Street\n Destination: Airport\n Time: 6:00 AM tomorrow\n Passengers: 1\n Do you confirm this booking?",
        "Yes, confirmed.",
        {
            "confirmed": True
        }
    ),
    (
        "Your taxi is booked! \nHave a safe trip to the airport! ",
        None,
        {}
    )
]

conversation2 = [
    (
        "Hi! How can I assist you with your taxi today?",
        "I need a taxi from Central Park to Grand Hotel at 8 PM tonight.",
        {
            "pickup_location": "Central Park",
            "destination": "Grand Hotel",
            "pickup_time": "8 PM tonight"
        }
    ),
    (
        "How many people will be traveling?",
        "There will be 4 of us. Can you send a bigger car, please?",
        {
            "passengers": 4,
            "special_requests": "bigger car"
        }
    ),
    (
        "Noted! I’ll arrange a larger vehicle for 4 passengers. \nAny other special requests?",
        "Could the driver please bring a child seat?",
        {
            "special_requests": "child seat"
        }
    ),
    (
        "Absolutely!\n Special request: Child seat\nHere’s your booking summary:\n- Pickup: Central Park\n- Destination: Grand Hotel\n- Time: 8:00 PM tonight\n- Passengers: 4\n- Special requests: Child seat\nDo you confirm this booking?",
        "Yes, that’s perfect.",
        {
            "confirmed": True
        }
    ),
    (
        "Confirmed! \nYour taxi will arrive at Central Park at 8:00 PM with a child seat. Have a great evening! ",
        None,
        {}
    )
]

conversation3 = [
    (
        "Hello! How can I help you book a taxi?",
        "Hi, I need a taxi tonight.",
        {}
    ),
    (
        "Sure! May I have your pickup location and destination, please?",
        "Pickup is Elm Street. I’m going to the train station.",
        {
            "pickup_location": "Elm Street",
            "destination": "train station"
        }
    ),
    (
        "Got it!\n Pickup: Elm Street\n Destination: Train station\nWhat time would you like the taxi tonight?",
        "Around 9 PM.",
        {
            "pickup_time": "9 PM tonight"
        }
    ),
    (
        "Thank you! How many passengers will be traveling?",
        "Just two.",
        {
            "passengers": 2
        }
    ),
    (
        "Great!\nHere’s your booking:\n- Pickup: Elm Street\n- Destination: Train station\n- Time: 9:00 PM tonight\n- Passengers: 2\n- Special requests: N/A\nPlease confirm if this is correct.",
        "Yes, thanks!",
        {
            "confirmed": True
        }
    ),
    (
        "Confirmed! \nYour taxi will be at Elm Street at 9:00 PM tonight. Have a safe trip!",
        None,
        {}
    )
]

all_conversations = [conversation1,conversation2,conversation3]