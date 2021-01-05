from radish import given, when, then
from bdd.core.utils.customers import get_customer_id_from_context

from bdd.oxygen.shell import oxygen_shell


@given(r"cashback category and merchant are added")
def given_category_and_merchant(step):
    """
    Add cashback category and merchant for next offers creating
    """
    response = oxygen_shell("cashback.create_merchant_and_category")
    assert response.data
    step.context.category_merchant_data = response.data


@given(r"created offer <{offer_name:w}>")
def given_created_offer(step, offer_name):
    """
    Create offer base on category and merchant data in step.context
    """
    response = oxygen_shell("cashback.create_offer", **step.context.category_merchant_data)
    assert response.data
    if not hasattr(step.context, 'offer_data'):
        step.context.offer_data = {}
    step.context.offer_data[offer_name] = {
        'id': response.data['offer_id']
    }


@given(r"created offer <{offer_name:w}> where min purchase is 20$")
def given_created_offer_where_purchase_is_shown(step, offer_name):
    """
    Create offer with visual default min_purchase funds amount
    """
    step.behave_like(f"Given created offer <{offer_name}>")


@given(r"activated card for <{customer_type:w}> customer")
def create_user_card(step, customer_type):
    """
    Activate card based on customer type
    """
    response = oxygen_shell(
        "cashback.create_card_for_user",
        customer_id=get_customer_id_from_context(step, customer_type)
    )
    assert response.data, response.data.get('card_id')


@when(r"activate cashback for user with offer <{offer_name:w}>")
def activate_cashback_for_user(step, offer_name):
    """
    Activate cashback offer by offer_name
    """
    offer = step.context.offer_data.get(offer_name)
    assert offer
    step.context.response = step.context.api("POST", f'cashback/offer/{offer["id"]}/activate/')


@when(r"deactivate cashback for user with offer <{offer_name:w}>")
def deactivate_cashback_for_user(step, offer_name):
    """
    Deactivate cashback offer by offer_name
    """
    offer = step.context.offer_data.get(offer_name)
    assert offer
    step.context.response = step.context.api("POST", f'cashback/offer/{offer["id"]}/deactivate/')


@when(r"user created transaction on <{amount:d}>$ by <{customer_type:w}> <{account_type:w}> account")
def create_transaction(step, customer_type, account_type, amount):
    """
    Create transaction based in funds amount, customer_type and account_type
    Category, merchant, account and user data are taking from step.context
    """
    user_id = step.context.credentials.get('user_id')
    assert user_id

    bank_account_id = step.context.accounts[customer_type][account_type]
    assert bank_account_id

    merchant_id = step.context.category_merchant_data.get('merchant_id')
    assert merchant_id

    response = oxygen_shell(
        "transaction.create_transaction",
        merchant_id=merchant_id,
        bank_account_id=bank_account_id,
        user_id=user_id,
        amount=amount,
    )
    transaction_id = response.data.get('transaction_id')
    assert response.data, transaction_id
    step.context.transaction = {
        'id': transaction_id
    }


@when('cashback for transaction was checked')
def check_cashback(step):
    """
    Check cashback by step.context transaction id
    """
    response = oxygen_shell(
        "cashback.check_cashback",
        transaction_id=step.context.transaction['id'],
    )
    assert response.ok, response.message


@then("cashback history count is <{count:d}>")
def check_cashback_history(step, count):
    """
    Check cashback history, compare that with predicted count of cashback entities
    """
    response = step.context.response = step.context.api("GET", 'cashback/history/')
    assert response.status_code == 200
    assert response.json()['count'] == count
