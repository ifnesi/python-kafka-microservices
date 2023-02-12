function viewOrder() {
    var order_id = document.getElementById("order_id_query").value;
    if (order_id) {
        window.location.href = "/orders/" + order_id;
    }
}

$(document).ready(function () {
    $('#order_id_query').on('keypress', function (e) {
        if (e.which === 13) {
            viewOrder();
        }
    });
});