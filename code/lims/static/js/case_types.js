// If the case_number_type is automatic,
// disable readonly on case_number_start.
$(document).ready( function () {
    if ($('#case_number_type').val() == 'Automatic') {
        $('#case_number_start').attr('disabled', false);
    } else {
        $('#case_number_start').attr('disabled', true);
        $('#case_number_start').val(1);
    }
})

// If the case_number_type is changed to manual,
// disable case_number_start.
$('#case_number_type').on('change', function () {
    if ($(this).val() == 'Automatic') {
        $('#case_number_start').attr('disabled', false);
        $('#case_number_start').val(1);
    } else {
        $('#case_number_start').attr('disabled', true);
        $('#case_number_start').val(1);
    }
})


