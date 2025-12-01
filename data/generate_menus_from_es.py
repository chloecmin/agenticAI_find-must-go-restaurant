import os
import csv
import random
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from dotenv import load_dotenv
from elasticsearch import Elasticsearch, helpers

# =====================
# 환경 변수 & ES 클라이언트 설정
# =====================

load_dotenv()

ES_HOST = os.getenv("ES_HOST")
ES_API_KEY = os.getenv("ES_API_KEY")
RESTAURANT_INDEX = os.getenv("ES_INDEX", "restaurants")  # 기본값 restaurants


SAMPLE_MENUS_BY_CUISINE = {
    "Afghani": [
        ("Kabuli Pulao", "main"),
        ("Afghani Chicken Karahi", "main"),
        ("Bolani Stuffed Flatbread", "side"),
    ],
    "African": [
        ("Jollof Rice with Grilled Chicken", "main"),
        ("Suya Spiced Beef Skewers", "main"),
        ("Plantain Chips", "side"),
    ],
    "American": [
        ("Classic Cheeseburger", "main"),
        ("Buttermilk Fried Chicken", "main"),
        ("Mac and Cheese", "side"),
    ],
    "Andhra": [
        ("Andhra Chilli Chicken", "main"),
        ("Gongura Mutton Curry", "main"),
        ("Pesarattu Dosa", "side"),
    ],
    "Arabian": [
        ("Mixed Grill Platter", "main"),
        ("Chicken Mandi Rice", "main"),
        ("Tabbouleh Salad", "side"),
    ],
    "Argentine": [
        ("Argentine Beef Asado", "main"),
        ("Chimichurri Steak", "main"),
        ("Empanadas de Carne", "side"),
    ],
    "Armenian": [
        ("Lula Kebab Plate", "main"),
        ("Armenian Lavash Wrap", "main"),
        ("Stuffed Grape Leaves", "side"),
    ],
    "Asian": [
        ("Stir-Fried Noodles with Vegetables", "main"),
        ("Asian Sesame Chicken Bowl", "main"),
        ("Crispy Spring Rolls", "side"),
    ],
    "Asian Fusion": [
        ("Kimchi Tacos", "main"),
        ("Sushi Burrito", "main"),
        ("Miso Glazed Wings", "side"),
    ],
    "Assamese": [
        ("Assamese Fish Curry", "main"),
        ("Aloo Pitika", "side"),
        ("Black Rice Pudding", "dessert"),
    ],
    "Australian": [
        ("Grilled Barramundi", "main"),
        ("Australian Beef Pie", "main"),
        ("Avocado Toast", "side"),
    ],
    "Awadhi": [
        ("Awadhi Dum Biryani", "main"),
        ("Nihari Gosht", "main"),
        ("Shami Kebab", "side"),
    ],
    "BBQ": [
        ("Smoked Ribs Platter", "main"),
        ("BBQ Pulled Pork Sandwich", "main"),
        ("Charred Corn on the Cob", "side"),
    ],
    "Bakery": [
        ("Butter Croissant", "dessert"),
        ("Chocolate Fudge Brownie", "dessert"),
        ("Cinnamon Roll", "dessert"),
    ],
    "Bar Food": [
        ("Loaded Nachos", "snack"),
        ("Buffalo Chicken Wings", "snack"),
        ("Beer-Battered Onion Rings", "snack"),
    ],
    "Belgian": [
        ("Belgian Waffle with Berries", "dessert"),
        ("Moules-Frites", "main"),
        ("Liege Sugar Waffle", "dessert"),
    ],
    "Bengali": [
        ("Kosha Mangsho", "main"),
        ("Shorshe Ilish", "main"),
        ("Mishti Doi", "dessert"),
    ],
    "Beverages": [
        ("Fresh Lime Soda", "drink"),
        ("Sparkling Fruit Punch", "drink"),
        ("Iced Lemon Tea", "drink"),
    ],
    "Bihari": [
        ("Litti Chokha", "main"),
        ("Bihari Kabab", "main"),
        ("Sattu Paratha", "side"),
    ],
    "Biryani": [
        ("Hyderabadi Chicken Biryani", "main"),
        ("Mutton Dum Biryani", "main"),
        ("Veg Handi Biryani", "main"),
    ],
    "Brazilian": [
        ("Feijoada Black Bean Stew", "main"),
        ("Churrasco Grilled Meats", "main"),
        ("Pão de Queijo", "side"),
    ],
    "Breakfast": [
        ("Pancake Stack with Syrup", "main"),
        ("Eggs Benedict", "main"),
        ("Granola Yogurt Bowl", "side"),
    ],
    "British": [
        ("Fish and Chips", "main"),
        ("Shepherd’s Pie", "main"),
        ("Sticky Toffee Pudding", "dessert"),
    ],
    "Bubble Tea": [
        ("Classic Milk Bubble Tea", "drink"),
        ("Taro Pearl Milk Tea", "drink"),
        ("Brown Sugar Boba Latte", "drink"),
    ],
    "Burger": [
        ("Double Beef Burger", "main"),
        ("Crispy Chicken Burger", "main"),
        ("Veggie Bean Burger", "main"),
    ],
    "Burmese": [
        ("Mohinga Noodle Soup", "main"),
        ("Tea Leaf Salad", "side"),
        ("Burmese Coconut Noodles", "main"),
    ],
    "Cafe": [
        ("Club Sandwich", "main"),
        ("Caesar Salad", "side"),
        ("Chocolate Chip Cookie", "dessert"),
    ],
    "Cajun": [
        ("Cajun Jambalaya Rice", "main"),
        ("Blackened Chicken", "main"),
        ("Cajun Fries", "side"),
    ],
    "Canadian": [
        ("Poutine with Gravy", "main"),
        ("Maple Glazed Salmon", "main"),
        ("Butter Tart", "dessert"),
    ],
    "Cantonese": [
        ("Cantonese Roast Duck", "main"),
        ("Sweet and Sour Pork", "main"),
        ("Steamed Egg Custard", "dessert"),
    ],
    "Caribbean": [
        ("Jerk Chicken Plate", "main"),
        ("Coconut Rice and Beans", "side"),
        ("Fried Plantain Slices", "side"),
    ],
    "Charcoal Grill": [
        ("Charcoal Grilled Lamb Chops", "main"),
        ("Smoky Chicken Skewers", "main"),
        ("Grilled Veggie Platter", "side"),
    ],
    "Chettinad": [
        ("Chettinad Chicken Curry", "main"),
        ("Pepper Mutton Fry", "main"),
        ("Kuzhi Paniyaram", "side"),
    ],
    "Chinese": [
        ("Kung Pao Chicken", "main"),
        ("Mapo Tofu with Rice", "main"),
        ("Vegetable Spring Rolls", "side"),
    ],
    "Coffee and Tea": [
        ("Cappuccino", "drink"),
        ("Matcha Latte", "drink"),
        ("Cold Brew Coffee", "drink"),
    ],
    "Contemporary": [
        ("Truffle Mushroom Risotto", "main"),
        ("Pan-Seared Salmon Fillet", "main"),
        ("Beetroot Goat Cheese Salad", "side"),
    ],
    "Continental": [
        ("Grilled Chicken Steak", "main"),
        ("Creamy Penne Alfredo", "main"),
        ("Garlic Bread Basket", "side"),
    ],
    "Cuban": [
        ("Cuban Sandwich", "main"),
        ("Ropa Vieja Beef Stew", "main"),
        ("Tostones Fried Plantains", "side"),
    ],
    "Cuisine Varies": [
        ("Chef’s Daily Special", "main"),
        ("Seasonal Tasting Platter", "main"),
        ("Mixed Appetizer Sampler", "side"),
    ],
    "Curry": [
        ("Butter Chicken Curry", "main"),
        ("Thai Green Curry", "main"),
        ("Vegetable Korma", "main"),
    ],
    "Deli": [
        ("Turkey Swiss Sandwich", "main"),
        ("Pastrami on Rye", "main"),
        ("Coleslaw Side Salad", "side"),
    ],
    "Desserts": [
        ("Classic Tiramisu", "dessert"),
        ("New York Cheesecake", "dessert"),
        ("Molten Chocolate Lava Cake", "dessert"),
    ],
    "Dim Sum": [
        ("Shrimp Har Gow Dumplings", "side"),
        ("Pork Siu Mai", "side"),
        ("Steamed BBQ Pork Buns", "side"),
    ],
    "Diner": [
        ("All-Day Breakfast Plate", "main"),
        ("Chicken Fried Steak", "main"),
        ("Thick-Cut Fries", "side"),
    ],
    "Drinks Only": [
        ("House Lemonade Pitcher", "drink"),
        ("Seasonal Mocktail", "drink"),
        ("Sparkling Mineral Water", "drink"),
    ],
    "Durban": [
        ("Durban Bunny Chow", "main"),
        ("Spicy Mutton Curry", "main"),
        ("Chili Bites Fritters", "side"),
    ],
    "European": [
        ("Herb Roasted Chicken", "main"),
        ("Creamy Mushroom Pasta", "main"),
        ("Mixed Green Salad", "side"),
    ],
    "Fast Food": [
        ("Crispy Chicken Nuggets", "main"),
        ("Double Patty Burger", "main"),
        ("French Fries", "side"),
    ],
    "Filipino": [
        ("Chicken Adobo", "main"),
        ("Pork Sisig", "main"),
        ("Halo-Halo Dessert", "dessert"),
    ],
    "Finger Food": [
        ("Mozzarella Sticks", "snack"),
        ("Mini Sliders", "snack"),
        ("Crispy Potato Wedges", "snack"),
    ],
    "Fish and Chips": [
        ("Classic Fish and Chips", "main"),
        ("Beer-Battered Cod Basket", "main"),
        ("Tartar Sauce Dip", "side"),
    ],
    "French": [
        ("Coq au Vin", "main"),
        ("Ratatouille Provençal", "main"),
        ("Crème Brûlée", "dessert"),
    ],
    "Fusion": [
        ("Teriyaki Chicken Tacos", "main"),
        ("Pasta with Kimchi Sauce", "main"),
        ("Sushi Nachos", "side"),
    ],
    "German": [
        ("Bratwurst with Sauerkraut", "main"),
        ("Schnitzel Plate", "main"),
        ("Pretzel with Mustard", "side"),
    ],
    "Goan": [
        ("Goan Fish Curry", "main"),
        ("Pork Vindaloo", "main"),
        ("Bebinca Layered Dessert", "dessert"),
    ],
    "Gourmet Fast Food": [
        ("Truffle Burger", "main"),
        ("Gourmet Hot Dog", "main"),
        ("Sweet Potato Fries", "side"),
    ],
    "Greek": [
        ("Chicken Souvlaki Plate", "main"),
        ("Moussaka Casserole", "main"),
        ("Greek Salad with Feta", "side"),
    ],
    "Grill": [
        ("Mixed Grill Platter", "main"),
        ("Grilled Chicken Skewers", "main"),
        ("Charred Veggie Skewers", "side"),
    ],
    "Gujarati": [
        ("Gujarati Thali", "main"),
        ("Khandvi Rolls", "side"),
        ("Undhiyu Mixed Vegetables", "main"),
    ],
    "Hawaiian": [
        ("Hawaiian Poke Bowl", "main"),
        ("Loco Moco Beef Plate", "main"),
        ("Spam Musubi", "side"),
    ],
    "Healthy Food": [
        ("Quinoa Buddha Bowl", "main"),
        ("Grilled Chicken Salad", "main"),
        ("Fresh Fruit Cup", "side"),
    ],
    "Hyderabadi": [
        ("Hyderabadi Dum Biryani", "main"),
        ("Mirchi Ka Salan", "side"),
        ("Double Ka Meetha", "dessert"),
    ],
    "Ice Cream": [
        ("Triple Scoop Sundae", "dessert"),
        ("Classic Vanilla Cone", "dessert"),
        ("Chocolate Brownie Sundae", "dessert"),
    ],
    "Indian": [
        ("Butter Chicken with Naan", "main"),
        ("Palak Paneer", "main"),
        ("Tandoori Platter", "side"),
    ],
    "Indonesian": [
        ("Nasi Goreng", "main"),
        ("Satay Chicken Skewers", "main"),
        ("Gado-Gado Salad", "side"),
    ],
    "International": [
        ("Global Tasting Plate", "main"),
        ("International Pasta Bowl", "main"),
        ("World Street Food Sampler", "side"),
    ],
    "Iranian": [
        ("Chelo Kebab Plate", "main"),
        ("Ghormeh Sabzi Stew", "main"),
        ("Saffron Rice with Zereshk", "side"),
    ],
    "Irish": [
        ("Irish Beef Stew", "main"),
        ("Corned Beef and Cabbage", "main"),
        ("Soda Bread Slice", "side"),
    ],
    "Italian": [
        ("Margherita Pizza", "main"),
        ("Spaghetti Carbonara", "main"),
        ("Tiramisu", "dessert"),
    ],
    "Izgara": [
        ("Izgara Mixed Grill", "main"),
        ("Grilled Lamb Kofte", "main"),
        ("Charred Vegetable Izgara", "side"),
    ],
    "Japanese": [
        ("Chicken Katsu Curry", "main"),
        ("Tempura Udon Noodles", "main"),
        ("Edamame with Sea Salt", "side"),
    ],
    "Juices": [
        ("Fresh Orange Juice", "drink"),
        ("Watermelon Cooler", "drink"),
        ("Carrot Apple Ginger Juice", "drink"),
    ],
    "Kashmiri": [
        ("Rogan Josh", "main"),
        ("Kashmiri Yakhni Pulao", "main"),
        ("Nadir Monje Fries", "side"),
    ],
    "Kebab": [
        ("Mixed Kebab Platter", "main"),
        ("Chicken Seekh Kebab", "main"),
        ("Lamb Shish Kebab Wrap", "main"),
    ],
    "Kerala": [
        ("Kerala Fish Curry", "main"),
        ("Appam with Stew", "main"),
        ("Banana Chips", "side"),
    ],
    "Kiwi": [
        ("Kiwi Fruit Tart", "dessert"),
        ("Kiwi Yogurt Parfait", "dessert"),
        ("Kiwi Lime Cooler", "drink"),
    ],
    "Korean": [
        ("Bibimbap Rice Bowl", "main"),
        ("Korean Fried Chicken", "main"),
        ("Kimchi Pancake", "side"),
    ],
    "Latin American": [
        ("Grilled Carne Asada", "main"),
        ("Chicken Enchiladas", "main"),
        ("Churros with Chocolate", "dessert"),
    ],
    "Lebanese": [
        ("Chicken Shawarma Plate", "main"),
        ("Hummus with Pita", "side"),
        ("Falafel Platter", "main"),
    ],
    "Lucknowi": [
        ("Lucknowi Galouti Kebab", "side"),
        ("Awadhi Biryani", "main"),
        ("Sheermal Bread", "side"),
    ],
    "Maharashtrian": [
        ("Misal Pav", "main"),
        ("Puran Poli", "dessert"),
        ("Vada Pav", "snack"),
    ],
    "Malay": [
        ("Nasi Lemak Malay Style", "main"),
        ("Beef Rendang", "main"),
        ("Roti Jala with Curry", "side"),
    ],
    "Malaysian": [
        ("Char Kway Teow", "main"),
        ("Laksa Noodle Soup", "main"),
        ("Roti Canai", "side"),
    ],
    "Malwani": [
        ("Malwani Fish Curry", "main"),
        ("Kombdi Vade", "main"),
        ("Solkadhi Drink", "drink"),
    ],
    "Mangalorean": [
        ("Mangalorean Chicken Sukka", "main"),
        ("Neer Dosa", "side"),
        ("Fish Gassi Curry", "main"),
    ],
    "Mediterranean": [
        ("Grilled Chicken Gyro Plate", "main"),
        ("Mediterranean Mezze Platter", "side"),
        ("Greek Yogurt with Honey", "dessert"),
    ],
    "Mexican": [
        ("Chicken Fajita Platter", "main"),
        ("Beef Tacos Trio", "main"),
        ("Nachos with Salsa", "side"),
    ],
    "Middle Eastern": [
        ("Mixed Shawarma Platter", "main"),
        ("Lamb Kofta with Rice", "main"),
        ("Baba Ganoush with Pita", "side"),
    ],
    "Mineira": [
        ("Feijão Tropeiro", "main"),
        ("Frango com Quiabo", "main"),
        ("Pão de Queijo Mineiro", "side"),
    ],
    "Mithai": [
        ("Gulab Jamun Bowl", "dessert"),
        ("Rasgulla Selection", "dessert"),
        ("Kaju Katli Slices", "dessert"),
    ],
    "Modern Australian": [
        ("Herb Crusted Lamb Rack", "main"),
        ("Seared Tuna with Salad", "main"),
        ("Ricotta Hotcake", "dessert"),
    ],
    "Modern Indian": [
        ("Truffle Butter Chicken", "main"),
        ("Paneer Tikka Skewers", "main"),
        ("Masala Prawn Risotto", "main"),
    ],
    "Moroccan": [
        ("Chicken Tagine with Olives", "main"),
        ("Lamb Couscous", "main"),
        ("Harira Soup", "side"),
    ],
    "Mughlai": [
        ("Mughlai Chicken Korma", "main"),
        ("Murgh Musallam", "main"),
        ("Roomali Roti Basket", "side"),
    ],
    "Naga": [
        ("Naga Pork Curry", "main"),
        ("Smoked Bamboo Shoot Stew", "main"),
        ("Axone Chilli Chutney", "side"),
    ],
    "Nepalese": [
        ("Nepalese Chicken Momos", "side"),
        ("Thukpa Noodle Soup", "main"),
        ("Dal Bhat Set", "main"),
    ],
    "New American": [
        ("BBQ Glazed Short Ribs", "main"),
        ("Truffle Mac and Cheese", "main"),
        ("Kale Caesar Salad", "side"),
    ],
    "North Eastern": [
        ("Smoked Pork with Bamboo Shoot", "main"),
        ("Rice Thali North Eastern Style", "main"),
        ("Steamed Sticky Rice Cake", "dessert"),
    ],
    "North Indian": [
        ("Dal Makhani with Naan", "main"),
        ("Paneer Butter Masala", "main"),
        ("Tandoori Chicken Tikka", "side"),
    ],
    "Oriya": [
        ("Odisha Fish Curry", "main"),
        ("Pakhala Bhaat", "main"),
        ("Chhena Poda", "dessert"),
    ],
    "Pakistani": [
        ("Chicken Karahi", "main"),
        ("Beef Nihari", "main"),
        ("Seekh Kebab Platter", "side"),
    ],
    "Parsi": [
        ("Dhansak with Brown Rice", "main"),
        ("Sali Boti", "main"),
        ("Lagan Nu Custard", "dessert"),
    ],
    "Patisserie": [
        ("Strawberry Mille-Feuille", "dessert"),
        ("Opera Cake Slice", "dessert"),
        ("Éclair Assortment", "dessert"),
    ],
    "Peranakan": [
        ("Ayam Buah Keluak", "main"),
        ("Laksa Peranakan", "main"),
        ("Kueh Lapis Slice", "dessert"),
    ],
    "Persian": [
        ("Joojeh Kebab Plate", "main"),
        ("Fesenjan Walnut Stew", "main"),
        ("Saffron Rice Tahdig", "side"),
    ],
    "Peruvian": [
        ("Lomo Saltado", "main"),
        ("Peruvian Ceviche", "side"),
        ("Aji de Gallina", "main"),
    ],
    "Pizza": [
        ("Margherita Pizza", "main"),
        ("Pepperoni Pizza", "main"),
        ("Four Cheese Pizza", "main"),
    ],
    "Portuguese": [
        ("Bacalhau à Brás", "main"),
        ("Piri Piri Chicken", "main"),
        ("Pastel de Nata", "dessert"),
    ],
    "Pub Food": [
        ("Bangers and Mash", "main"),
        ("Classic Pub Burger", "main"),
        ("Loaded Potato Skins", "side"),
    ],
    "Rajasthani": [
        ("Dal Baati Churma", "main"),
        ("Laal Maas", "main"),
        ("Ghevar Sweet", "dessert"),
    ],
    "Ramen": [
        ("Tonkotsu Ramen Bowl", "main"),
        ("Shoyu Ramen with Egg", "main"),
        ("Spicy Miso Ramen", "main"),
    ],
    "Raw Meats": [
        ("Steak Tartare Plate", "main"),
        ("Carpaccio of Beef", "main"),
        ("Salmon Sashimi Platter", "side"),
    ],
    "Restaurant Cafe": [
        ("Grilled Chicken Panini", "main"),
        ("Roasted Veggie Quiche", "main"),
        ("House Salad Bowl", "side"),
    ],
    "Salad": [
        ("Caesar Chicken Salad", "main"),
        ("Greek Feta Salad", "main"),
        ("Quinoa Avocado Salad", "main"),
    ],
    "Sandwich": [
        ("Grilled Cheese Sandwich", "main"),
        ("Chicken Club Sandwich", "main"),
        ("Veggie Hummus Sandwich", "main"),
    ],
    "Scottish": [
        ("Haggis with Neeps and Tatties", "main"),
        ("Scottish Salmon Fillet", "main"),
        ("Cranachan Dessert", "dessert"),
    ],
    "Seafood": [
        ("Grilled Seafood Platter", "main"),
        ("Garlic Butter Prawns", "main"),
        ("Calamari Rings", "side"),
    ],
    "Singaporean": [
        ("Hainanese Chicken Rice", "main"),
        ("Chilli Crab", "main"),
        ("Kaya Toast Set", "side"),
    ],
    "Soul Food": [
        ("Fried Chicken and Waffles", "main"),
        ("Collard Greens with Bacon", "side"),
        ("Southern Cornbread", "side"),
    ],
    "South African": [
        ("Bobotie with Yellow Rice", "main"),
        ("Boerewors Sausage Roll", "main"),
        ("Melktert Custard Tart", "dessert"),
    ],
    "South American": [
        ("Grilled Picanha Steak", "main"),
        ("Arepa Stuffed Pockets", "main"),
        ("Chimichurri Potato Salad", "side"),
    ],
    "South Indian": [
        ("Masala Dosa with Sambar", "main"),
        ("Idli Vada Combo", "main"),
        ("Curd Rice", "side"),
    ],
    "Southern": [
        ("Buttermilk Fried Chicken", "main"),
        ("Biscuits and Gravy", "side"),
        ("Pecan Pie Slice", "dessert"),
    ],
    "Southwestern": [
        ("Southwestern Chicken Bowl", "main"),
        ("Beef Chili with Beans", "main"),
        ("Cornbread Muffins", "side"),
    ],
    "Spanish": [
        ("Paella Valenciana", "main"),
        ("Patatas Bravas", "side"),
        ("Churros con Chocolate", "dessert"),
    ],
    "Sri Lankan": [
        ("Sri Lankan Rice and Curry", "main"),
        ("Egg Hopper", "main"),
        ("Pol Sambol Coconut Relish", "side"),
    ],
    "Steak": [
        ("Ribeye Steak with Sides", "main"),
        ("Sirloin Steak Plate", "main"),
        ("Steak Sandwich", "main"),
    ],
    "Street Food": [
        ("Loaded Street Tacos", "main"),
        ("Fried Dumpling Bites", "side"),
        ("Spicy Street Noodles", "main"),
    ],
    "Sunda": [
        ("Sundanese Nasi Timbel", "main"),
        ("Grilled Gurame Fish", "main"),
        ("Lalapan Fresh Salad", "side"),
    ],
    "Sushi": [
        ("Assorted Nigiri Sushi", "main"),
        ("Salmon Maki Roll", "main"),
        ("California Roll Platter", "main"),
    ],
    "Taiwanese": [
        ("Taiwanese Beef Noodle Soup", "main"),
        ("Gua Bao Pork Buns", "side"),
        ("Salt and Pepper Chicken", "main"),
    ],
    "Tapas": [
        ("Spanish Tapas Platter", "side"),
        ("Garlic Shrimp Tapas", "side"),
        ("Chorizo in Red Wine", "side"),
    ],
    "Tea": [
        ("English Breakfast Tea Pot", "drink"),
        ("Jasmine Green Tea", "drink"),
        ("Masala Chai Latte", "drink"),
    ],
    "Teriyaki": [
        ("Chicken Teriyaki Rice Bowl", "main"),
        ("Salmon Teriyaki Plate", "main"),
        ("Teriyaki Veggie Stir-Fry", "main"),
    ],
    "Tex-Mex": [
        ("Beef Burrito Bowl", "main"),
        ("Chicken Quesadilla", "main"),
        ("Chips with Queso Dip", "side"),
    ],
    "Thai": [
        ("Pad Thai Noodles", "main"),
        ("Green Curry with Rice", "main"),
        ("Tom Yum Soup", "side"),
    ],
    "Tibetan": [
        ("Tibetan Thukpa Soup", "main"),
        ("Steamed Beef Momos", "side"),
        ("Butter Tea", "drink"),
    ],
    "Turkish": [
        ("Doner Kebab Plate", "main"),
        ("Iskender Kebab", "main"),
        ("Baklava Dessert", "dessert"),
    ],
    "Turkish Pizza": [
        ("Lahmacun Turkish Pizza", "main"),
        ("Pide with Cheese and Meat", "main"),
        ("Spicy Turkish Salad", "side"),
    ],
    "Vegetarian": [
        ("Vegetarian Lasagna", "main"),
        ("Grilled Veggie Skewers", "main"),
        ("Roasted Veggie Salad", "side"),
    ],
    "Vietnamese": [
        ("Beef Pho Noodle Soup", "main"),
        ("Bánh Mì Sandwich", "main"),
        ("Fresh Spring Rolls", "side"),
    ],
    "Western": [
        ("Grilled Chicken with Mash", "main"),
        ("Beef Steak with Fries", "main"),
        ("House Garden Salad", "side"),
    ],
    "World Cuisine": [
        ("World Street Food Sampler", "main"),
        ("Global Curry Platter", "main"),
        ("International Tapas Board", "side"),
    ],
}


import random
import csv
import re
from elasticsearch import Elasticsearch, helpers


OUTPUT_CSV = "data/restaurants_menus.csv"


def parse_cuisines(value):
    """
    ES의 cuisines 필드를 파싱해서 리스트로 변환.
    - list 인 경우 그대로 사용
    - 문자열인 경우 ',', '/' 기준으로 split
    """
    if value is None:
        return []

    if isinstance(value, list):
        return [c.strip() for c in value if c and isinstance(c, str)]

    if isinstance(value, str):
        parts = re.split(r"[,/]", value)
        return [c.strip() for c in parts if c.strip()]

    return []


def fetch_restaurants(es: Elasticsearch):
    """
    restaurants 인덱스에서 모든 레스토랑의
    restaurant_id, restaurant_name, cuisines 만 가져오기
    """
    query = {"query": {"match_all": {}}}

    for doc in helpers.scan(
        es,
        index=RESTAURANT_INDEX,
        query=query,
        _source=["restaurant_id", "restaurant_name", "cuisines"],
    ):
        src = doc["_source"]

        restaurant_id = src.get("restaurant_id") or src.get("id") or doc["_id"]
        restaurant_name = src.get("restaurant_name") or src.get("name")

        cuisines_raw = src.get("cuisines")
        cuisines_parsed = parse_cuisines(cuisines_raw)

        yield {
            "restaurant_id": restaurant_id,
            "restaurant_name": restaurant_name,
            "cuisines_parsed": cuisines_parsed,
        }


def generate_price():
    """7,000 ~ 35,000원 사이 500원 단위 랜덤 가격"""
    return random.randrange(7000, 35001, 500)


def generate_is_recommended(p=0.8):
    """80% 확률로 1, 20% 확률로 0"""
    return 1 if random.random() < p else 0


def main():
    es = Elasticsearch(ES_HOST)

    # 1) 레스토랑 전체 가져오기
    restaurants = list(fetch_restaurants(es))
    print(f"총 레스토랑 수: {len(restaurants)}")

    rows = []

    for r in restaurants:
        restaurant_id = r["restaurant_id"]
        restaurant_name = r["restaurant_name"]
        cuisines_parsed = r["cuisines_parsed"]  # 예: ["Korean", "BBQ"]

        if not cuisines_parsed:
            continue

        for cuisine in cuisines_parsed:
            cuisine = cuisine.strip()
            if not cuisine:
                continue

            # dict에서 해당 cuisine의 샘플 메뉴 3개 가져오기
            menus = SAMPLE_MENUS_BY_CUISINE.get(cuisine)
            if not menus:
                # ES에 있는 cuisine 문자열이 dict 키랑 안 맞으면 스킵됨
                continue

            for menu_name, menu_category in menus:
                row = {
                    "restaurant_id": restaurant_id,
                    "restaurant_name": restaurant_name,
                    # 여기 menu_type 에는 ES의 cuisine 값 그대로
                    "menu_type": cuisine,
                    "menu_name": menu_name,
                    # main / side / dessert / drink 등
                    "menu_category": menu_category,
                    "price": generate_price(),
                    "is_recommended": generate_is_recommended(p=0.8),
                }
                rows.append(row)

    # 2) CSV로 저장
    fieldnames = [
        "restaurant_id",
        "restaurant_name",
        "menu_type",      # = cuisine
        "menu_name",
        "menu_category",  # main / side / dessert / drink ...
        "price",
        "is_recommended",
    ]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"총 생성된 메뉴 row 수: {len(rows)}")
    print(f"CSV 저장 완료: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
