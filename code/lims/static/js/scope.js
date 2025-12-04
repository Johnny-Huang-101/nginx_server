
// If internal standard is "No",  disable internal_standard_conc field
$('#internal_standard').on('change', function () {
    if ($('#internal_standard').val() == 'Yes') {
        $('#internal_standard_conc').attr('disabled', false);
    } else {
        $('#internal_standard_conc').attr('diabled', true);
        $('#internal_standard_conc').val("");
    }
});