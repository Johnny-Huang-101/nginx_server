
// Enable parent_selection field if the user selects "Field" in the type
function disableParentSection() {
    if  ($('#type').val() == 'Field') {
            $('#parent_section').prop('disabled', false)
        } else {
            $('#parent_section').prop('disabled', true)
        }
        $('#parent_section').selectpicker('val', 0)
        $('#parent_section').selectpicker('refresh')
}

$(document).ready(disableParentSection)
$('#type').on('change', disableParentSection)