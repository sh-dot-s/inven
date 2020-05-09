import mongoengine
from mongoengine import Document, StringField, IntField, ListField

mongoengine.connect('test', host='localhost:27017')


class Order(Document):
    buyer_name = StringField(required=True, default="Hitesh")
    items = ListField(required=True)
    category = ListField(required=True)
    amount = IntField(required=True)
    order_status = StringField(required=True, default="PENDING")
    address = StringField(required=True)
    missing_items = ListField(required=False)
