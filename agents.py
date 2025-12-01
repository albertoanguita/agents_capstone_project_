import datetime

from google.adk.agents import Agent, LlmAgent, SequentialAgent, BaseAgent
from google.adk.tools import google_search, ToolContext, FunctionTool


def get_coordinator_agent(model: str = "gemini-2.5-flash-lite") -> BaseAgent:
    coordinator_agent = SequentialAgent(
        name="coordinator",
        description="A coordinator agent for designing a weekly menu.",
        sub_agents=[get_nutritionist_agent(model),
                    get_menu_designer_agent(model),
                    get_ingredient_finder_agent(model),
                    get_shopping_agent(model)],
    )

    return coordinator_agent


def get_nutritionist_agent(model: str = "gemini-2.5-flash-lite") -> Agent:
    nutritionist_agent = LlmAgent(
        name="nutritionist",
        model=model,
        description="A agent emulating a nutritionist for designing healthy menus according to user requests or goals.",
        instruction="You are a nutritionist. Your goal is to design healthy menus for a user. You will receive general "
                    "data about the user (sex, age, weight, height) plus the goal he is aiming for "
                    "(e.g. 'I want to loose weight', or 'I want to gain muscle'). You will output the guidelines for the "
                    "menus of a whole week, setting the appropriate proportion of proteins, fat and "
                    "carbohydrates in each meal, as well as total calories. You will use well established knowledge in modern medicine, as a "
                    "nutritionist would do, to provide solid answers.",
        output_key="menu_guidelines",
    )

    return nutritionist_agent


def get_menu_designer_agent(model: str = "gemini-2.5-flash-lite") -> Agent:
    menu_designer_agent = LlmAgent(
        name="menu_designer",
        model=model,
        description="A agent for designing daily menus for the user.",
        instruction="You are chef in charge of creating menus for a user. Menus must strictly conform to the menu "
                    "guidelines received in {menu_guidelines}, which provide instructions amount of calories and "
                    "percentages of fat, protein and carbohydrates. You are allowed to play with the received values "
                    "a bit, but overall you must follow them. Use the established knowledge, but also google search "
                    "to find which ingredients you are allowed to use and what recipes you could prepare with them. "
                    "The output must be, for each day of the week, three full means (breakfast, lunch and dinner), each "
                    "consisting of the individual plates of the meal. If a plate is a bit complicated, you should "
                    "provide a link to the corresponding recipe",
        tools=[google_search],
        output_key="menu_design",
    )

    return menu_designer_agent


def get_ingredient_finder_agent(model: str = "gemini-2.5-flash-lite") -> Agent:
    ingredient_finder_agent = LlmAgent(
        name="ingredient_finder",
        model=model,
        description="An agent in charge of finding ingredients in online stores.",
        instruction="You are a web search assistant. You receive the menu for a whole week in {menu_design} "
                    "and you must find web stores where acquiring the necessary ingredients for preparing all the means in the menu. Use "
                    "google search to find places where buying the required ingredients. You "
                    "will produce a list of ingredients, together with a link to the web selling it, the quantity to "
                    "acquire and the total price of the ingredient. You will produce one line per ingredient. Each "
                    "line will have the following format: 'ingredient name,link,quantity,price', the price being that of one "
                    "quantity of the ingredient (in euros). Do not include the currency in the price field, only the number. You must not include "
                    "anything else in the output, apart from the lines with the aforementioned format",
        tools=[google_search],
        output_key="ingredient_webs",
    )

    return ingredient_finder_agent


def get_shopping_agent(model: str = "gemini-2.5-flash-lite") -> Agent:
    shopping_agent = LlmAgent(
        name="shopper",
        model=model,
        description="An agent in charge of acquiring ingredients from web stores.",
        instruction="""You are a shopping-enabled agent. You receive a list of ingredients in {ingredient_webs}, and you must place an order for buying them
                    "When you receive a list of ingredients:
                    1. Use the place_shipping_order tool with {ingredient_webs} (pass the argument as is, the tool will parse it appropriately)
                    2. If the order status is 'pending', inform the user that approval is required
                    3. After receiving the final result, provide a clear summary including:
                      - Order status (approved/rejected)
                      - Order ID (if available)
                      - Number of ingredients and tota price
                    4. Keep responses concise but informative""",
        tools=[FunctionTool(func=place_ingredients_order)],
    )

    return shopping_agent


class ingredient_order:
    def __init__(self, line: str):
        data = line.split(",")
        self.ingredient = data[0]
        self.url = data[1]
        self.quantity = data[2]
        self.price = float(data[3])


def place_ingredients_order(
        ingredients: str, tool_context: ToolContext
) -> dict:
    """Creates a shopping order. Requires approval if ordering more than 100 euros (LARGE_ORDER_THRESHOLD).

    Args:
        num_containers: Number of containers to ship
        destination: Shipping destination

    Returns:
        Dictionary with order status
    """

    print("place_shipping_order start...")
    ingredient_list = ingredients.split("\n")
    print(f"place_shipping_order received {len(ingredient_list)} lines. Parsing...")

    parsed_ingredients = [ingredient_order(line) for line in ingredient_list]
    num_ingredients = len(parsed_ingredients)

    print(f"Received ingredients order with {num_ingredients} amount of items")

    total_price = 0
    for ingredient in parsed_ingredients:
        total_price += ingredient.price

    now = datetime.datetime.now()
    order_id_base = f'INGREDIENT-ORDER-{num_ingredients}_{now.year}-{now.month}-{now.day}'

    print(f"Total amount of request is {total_price}. Order id base is {order_id_base}")

    # -----------------------------------------------------------------------------------------------
    # -----------------------------------------------------------------------------------------------
    # SCENARIO 1: Small orders (≤100 euros) auto-approve
    if total_price <= 50:
        print(f"Order is self approved")
        return {
            "status": "approved",
            "order_id": f"{order_id_base}-AUTO",
            "num_ingredients": num_ingredients,
            "total_price": total_price,
            "message": f"Order auto-approved: {num_ingredients} ingredients for {total_price}",
        }

    # -----------------------------------------------------------------------------------------------
    # -----------------------------------------------------------------------------------------------
    # SCENARIO 2: This is the first time this tool is called. Large orders need human approval - PAUSE here.
    if not tool_context.tool_confirmation:
        print(f"Order requires confirmation")
        tool_context.request_confirmation(
            hint=f"⚠️ Large order: {total_price} euros. Do you want to approve?",
            payload={"total_price": total_price, "num_ingredients": num_ingredients},
        )
        return {  # This is sent to the Agent
            "status": "pending",
            "message": f"{num_ingredients} for {total_price} euros requires approval",
        }

    # -----------------------------------------------------------------------------------------------
    # -----------------------------------------------------------------------------------------------
    # SCENARIO 3: The tool is called AGAIN and is now resuming. Handle approval response - RESUME here.
    if tool_context.tool_confirmation.confirmed:
        print(f"Order requiring confirmation has been approved")
        return {
            "status": "approved",
            "order_id": f"{order_id_base}-HUMAN",
            "num_ingredients": num_ingredients,
            "total_price": total_price,
            "message": f"Order approved: {num_ingredients} for {total_price}",
        }
    else:
        print(f"Order requiring confirmation has been denied")
        return {
            "status": "rejected",
            "message": f"Order rejected: {num_ingredients} for {total_price}",
        }
