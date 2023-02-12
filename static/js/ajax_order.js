var order_id;
var last_result;

// Update view order every 1 sec (in a realistic scenario that would be better off using REACT)
function update_order_status() {
    if (order_id) {
        $.ajax({
            type: "POST",
            async: true,
            url: "/orders/" + order_id,
            dataType: "json",
            success: function (data) {
                if (data) {
                    if (last_result != 400) {
                        last_result = data.status;
                        $("#order_status").text(data.str);
                        setTimeout(function () {
                            update_order_status();
                        }, 1000);
                    }
                }
            }
        });
    }
}

$(document).ready(function () {
    order_id = $("#order_id").val();
    setTimeout(function () {
        update_order_status();
    }, 1000);
});