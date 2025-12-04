

// Get divisions for selected submitting agency
$('#agency_id').on('change', function (){
    $.getJSON('/default_clients/get_divisions/', {
        agency_id: $(this).val(),
    }, function(data) {
        var optionHTML = '';
        for (var choice of data.divisions) {
            optionHTML += '<option value="' + choice.id + '">' + choice.name + '</option>';
        }
        $('#division_id').html(optionHTML);
        $('#division_id').selectpicker('refresh')
        $('#division_id').selectpicker('render')

    });
    return false;
})
