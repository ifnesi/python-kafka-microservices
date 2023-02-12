function viewOrder() {
    var order_id = document.getElementById("order_id").value;
    if (order_id) {
        window.location.href = "/orders/" + order_id;
    }
}