$('#include_date_range').on('click', function () {
    var checked = $(this).prop('checked')
    console.log(checked);
     if (checked) {
        $('#start_date').attr('disabled', false)
        $('#end_date').attr('disabled', false)
    } else {
        $('#start_date').attr('disabled', true)
        $('#start_date').val("")
        $('#end_date').attr('disabled', true)
        $('#end_date').val("")
    }
})

$('#form').on('submit', function() {
    $('#processing').modal('hide');
    $('#submit').attr('disabled', false);
});
