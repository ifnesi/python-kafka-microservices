function viewOrder() {
    var order_id = document.getElementById("order_id_query").value;
    if (order_id) {
        window.location.href = "/orders/" + order_id;
    }
}

$(document).ready(function () {
    // Handle Enter key press for order search
    $('#order_id_query').on('keypress', function (e) {
        if (e.which === 13) {
            viewOrder();
        }
    });

    // Bootstrap 5 form validation
    const forms = document.querySelectorAll('.needs-validation');
    Array.from(forms).forEach(form => {
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            } else {
                // Disable submit button and show loading state
                const submitBtn = form.querySelector('[type="submit"]');
                if (submitBtn) {
                    submitBtn.disabled = true;
                    submitBtn.style.cursor = 'wait';
                    const originalText = submitBtn.innerHTML;
                    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Processing...';
                }
            }
            form.classList.add('was-validated');
        }, false);
    });

    // Add smooth scroll behavior
    document.documentElement.style.scrollBehavior = 'smooth';
});