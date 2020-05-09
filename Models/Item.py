import datetime

import mongoengine
from mongoengine import Document, StringField, IntField, DateTimeField, fields

mongoengine.connect('test', host='localhost:27017')


class Item(Document):
    vendor_name = StringField(required=True)
    item_name = StringField(required=True)
    category = StringField(required=True)
    description = StringField(required=False)
    item_count = IntField(required=True)
    item_price = IntField(required=True)
    date_time = DateTimeField(default=datetime.datetime.now)
    item_image = fields.ImageField(thumbnail_size=(150, 150, False))

    def to_json(self, *args, **kwargs):
        return dict(
            vendor_name=self.vendor_name,
            item_name=self.item_name,
            category=self.category,
            description=self.description,
            item_count=self.item_count,
            item_price=self.item_price,
            item_image=self.item_image,
            id=self.pk
        )
