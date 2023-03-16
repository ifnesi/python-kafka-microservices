var order_id;
var status_delivered;
var last_result = -1;

$(document).ready(function () {
    order_id = $("#order_id").val();
    status_delivered = $("#status_delivered").val();
    setTimeout(function () {
        update_order_status();
    }, 3000);
});

function toggle_status(remove, add) {
    $("#order_status").removeClass(remove);
    $("#order_status").addClass(add);
}

// Update view order every 3 secs (in a realistic scenario that would be better off using REACT)
function update_order_status() {
    if (order_id) {
        $.ajax({
            type: "PUT",
            async: true,
            url: "/orders/" + order_id,
            dataType: "json",
            success: function (data) {
                if (data) {
                    if (last_result != status_delivered) {
                        $("#order_status").text(data.str);
                        setTimeout(function () {
                            update_order_status();
                        }, 3000);
                    }
                    if (data.status == status_delivered) {
                        toggle_status("badge-info", "badge-success");
                    }
                    else if (last_result != data.status && last_result != -1) {
                        var timeout;
                        for (var i = 0; i < 3; i++) {
                            timeout = i * 500;
                            setTimeout(function () {
                                toggle_status("badge-info", "badge-warning");
                            }, timeout);
                            setTimeout(function () {
                                toggle_status("badge-warning", "badge-info");
                            }, 250 + timeout);
                        }
                    }
                    last_result = data.status;
                }
            }
        });
    }
}
