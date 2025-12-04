$(function() {
    // Function to enable the specimen_types select field
    function enableSpecimenTypes() {
        $('#specimen_types').prop('disabled', false);
        $('#specimen_types').selectpicker('refresh');  // If using selectpicker
    }

    // Function to populate specimen types and update discipline
//    function populateSpecimenTypes(button) {
//        // Send a getJSON request to populate specimen_types based on the button value
//        $.getJSON('/autopsy_view_buttons/get_specimen_types', {
//            button: button,  // Send 'button' instead of 'discipline'
//        }, function(data) {
//            var options = '';
//            for (var item of data.choices) {
//                options += '<option value="' + item.id + '">' + item.name + '</option>';
//            }
//
//            // Populate the specimen_types select field with the returned choices
//            $('#specimen_types').html(options);
//            $('#specimen_types').selectpicker('refresh');
//            $('#specimen_types').selectpicker('render');
//
//            // Update the discipline selectpicker value to the returned discipline
//            $('#discipline').selectpicker('val', data.discipline);
//        });
//    }

    // Event handler for button change
    $('#button').on('change', function() {
        var button = $('#button').val();  // Get the value of the 'button' element

        // Enable specimen_types when button changes
        if (button !== '0') {  // Check if button is not 0
            enableSpecimenTypes();
            populateSpecimenTypes(button);
        }

        return false;
    });

    // Document ready logic
    $(document).ready(function() {
        var button = $('#button').val();  // Get the value of the 'button' element on page load

        // Enable specimen_types and populate if button is not 0 on page load
        if (button !== '0' && button !== '') {  // Ensure button has a valid value
            enableSpecimenTypes();
            populateSpecimenTypes(button);  // Call the function to populate on page load
        }
    });
});
