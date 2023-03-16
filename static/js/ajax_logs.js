$(document).ready(function () {
    order_id = $("#order_id").val();
    status_delivered = $("#status_delivered").val();
    setTimeout(function () {
        get_logs();
    }, 1000);
});

// Update view order every 1 sec (in a realistic scenario that would be better off using REACT)
function get_logs() {
    $.ajax({
        type: "PUT",
        async: true,
        url: "/logs",
        success: function (data) {
            if (data) {
                $("#log_data").html(data);
                setTimeout(function () {
                    get_logs();
                }, 1000);
            }
        }
    });
}
