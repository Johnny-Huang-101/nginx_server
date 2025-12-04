$(function() {
    $('#solution_type_id').on('change', function() {

        console.log('TEST')

        solution_type = $('#solution_type_id').val();

         $.getJSON('/standards_and_solutions/get_constituents/', {
            solution_type: solution_type,
            }, function(data) {
                var options = '';
                for (var item of data.choices) {
                    options += '<option value="' + item.id + '">' + item.name + '</option>';
                }

                console.log(options)

                $('#constituent').html(options)
                $('#constituent').selectpicker('refresh')
                $('#constituent').selectpicker('render')
                $('#constituent').selectpicker('val', 0)

            });
            return false;
    });

    $(window).on('load', function() {

        solution_type = $('#solution_type_id').val();

         $.getJSON('/standards_and_solutions/get_constituents/', {
            solution_type: solution_type,
            }, function(data) {
                var options = '';
                for (var item of data.choices) {
                    options += '<option value="' + item.id + '">' + item.name + '</option>';
                }

                $('#constituent').html(options)
                $('#constituent').selectpicker('refresh')
                $('#constituent').selectpicker('render')
                $('#constituent').selectpicker('val', 0)
                populateConstituentData(table, id);
            });
            return false;
    });

    // Function to fetch and populate data based on item data
    function populateConstituentData(table, id) {
        $.getJSON('/standards_and_solutions/get_constituent_data/', { table: table, id: id }, function(data) {
            console.log('IN FUNC')
            // Update the field with the name "constituent"
            console.log('DATA CONST', data.constituent);
            $('#constituent').val(data.constituent).selectpicker('refresh');
            console.log('CONST UPDATED');
        });
    }

    // Extract table and id from URL
    var pathArray = window.location.pathname.split('/');
    var table = pathArray[1]; // Assuming the table is the second segment
    var id = pathArray[2];    // Assuming the id is the third segment

    console.log('TABLE', table);
    console.log('ID', id);

});

function disableExpiryDate() {
    //disable the expiry date field if the "no expiry date" check box
    // is checked
    var checked = $('#no_exp_date').prop('checked')
    if (checked) {
        $('#exp_date').prop('disabled', true)
        $('#exp_date').val("")
    } else {
        $('#exp_date').prop('disabled', false)
    }
}
// run script on page render and on click event
$(document).ready(disableExpiryDate)
$('#no_exp_date').on('click',disableExpiryDate)

//const reagent = ['3']
//
//window.addEventListener('load', sTypeSelected);
//
//function sTypeSelected(){
//
//    var sType = document.getElementById('solution_type_id').selectedOptions[0].value;
//    console.log(sType)
//
//    if (reagent.includes(sType)) {
//        $('#const_div').css('display', 'none');
//    } else {
//        $('#const_div').css('display', 'block');
//    }
//}