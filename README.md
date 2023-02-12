# python-kafka-microservices
Based on: https://www.confluent.io/en-gb/blog/event-driven-microservices-with-python-and-kafka/

# STILL NOT FINISHED, PENDING TESTS AND DOCS!!!

## Service Flow
![image](docs/service_flow.png)

## CQRS Architecture using Confluent Cloud (Apache Kafka Cluster)
![image](docs/architecture_cqrs.png)


## Example of chronology of events:
Order submitted (webapp):
```
(webapp) INFO 21:00:39.603 - Event successfully produced
 - Topic 'pizza-ordered', Partition #5, Offset #18
 - Key: 3c91b
 - Value: {"status": 100, "timestamp": 1676235639159, "order": {"extra_toppings": ["Mushroom", "Black olives", "Green pepper"], "customer_id": "d94a6c43d9f487c1bef659f05c002213", "name": "Italo", "sauce": "Tomato", "cheese": "Mozzarella", "main_topping": "Pepperoni"}}
 ```

Microservice Deliver Pizza (step 1/2: receive early warning about a new order by subscribing to topic ```pizza-ordered```)
```
(msvc_delivery) INFO 21:00:18.516 - Subscribed to topic(s): pizza-ordered, pizza-baked
(msvc_delivery) INFO 21:00:39.609 - Early warning to deliver order '3c91b' to customer_id 'd94a6c43d9f487c1bef659f05c002213'
```

 Microservice Assemble Pizza (started once order is submitted by subscribing to topic ```pizza-ordered```):
 ```
(msvc_assemble) INFO 21:00:08.500 - Subscribed to topic(s): pizza-ordered
(msvc_assemble) INFO 21:00:39.604 - Preparing order '3c91b', assembling time is 4 second(s)
(msvc_assemble) INFO 21:00:43.608 - Order '3c91b' is assembled!
(msvc_assemble) INFO 21:00:43.923 - Event successfully produced
 - Topic 'pizza-assembled', Partition #5, Offset #15
 - Key: 3c91b
 - Value: {"baking_time": 17}
(msvc_assemble) INFO 21:00:44.847 - Event successfully produced
 - Topic 'pizza-status', Partition #5, Offset #45
 - Key: 3c91b
 - Value: {"status": 200}
 ```

 Microservice Process Status (started whenever order status is changed by subscribing to topic ```pizza-status```):
 ```
(msvc_status) INFO 21:00:12.579 - Subscribed to topic(s): pizza-status
(msvc_status) INFO 21:00:44.851 - Order '3c91b' status updated: Your pizza is in the oven (200)
 ```

Microservice Bake Pizza (started once pizza is assembled by subscribing to topic ```pizza-assembled```)
```
(msvc_bake) INFO 21:00:15.319 - Subscribed to topic(s): pizza-assembled
(msvc_bake) INFO 21:00:43.927 - Preparing order '3c91b', baking time is 17 second(s)
(msvc_bake) INFO 21:01:00.929 - Order '3c91b' is baked!
(msvc_bake) INFO 21:01:01.661 - Event successfully produced
 - Topic 'pizza-baked', Partition #5, Offset #15
 - Key: 3c91b
 - Value:
(msvc_bake) INFO 21:01:02.645 - Event successfully produced
 - Topic 'pizza-status', Partition #5, Offset #46
 - Key: 3c91b
 - Value: {"status": 300}
```

Microservice Process Status (started whenever order status is changed by subscribing to topic ```pizza-status```):
```
(msvc_status) INFO 21:00:12.579 - Subscribed to topic(s): pizza-status
(msvc_status) INFO 21:01:02.647 - Order '3c91b' status updated: Your pizza is out for delivery (300)
 ```

Microservice Deliver Pizza (step 2/2: started once pizza is baked by subscribing to topic ```pizza-baked```)
```
(msvc_delivery) INFO 21:00:18.516 - Subscribed to topic(s): pizza-ordered, pizza-baked
(msvc_delivery) INFO 21:01:01.662 - Deliverying order '3c91b' for customer_id 'd94a6c43d9f487c1bef659f05c002213', delivery time is 10 second(s)
(msvc_delivery) INFO 21:01:11.665 - Order '3c91b' delivered to customer_id 'd94a6c43d9f487c1bef659f05c002213'
(msvc_delivery) INFO 21:01:12.899 - Event successfully produced
 - Topic 'pizza-status', Partition #5, Offset #47
 - Key: 3c91b
 - Value: {"status": 400}
```

Microservice Process Status (started whenever order status is changed by subscribing to topic ```pizza-status```):
```
(msvc_status) INFO 21:00:12.579 - Subscribed to topic(s): pizza-status
(msvc_status) INFO 21:01:12.902 - Order '3c91b' status updated: Your pizza was delivered (400)
 ```