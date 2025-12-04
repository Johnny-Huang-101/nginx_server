
$(function() {
    $('#solution_type_id').on('change', function() {

        solution_type = $('#solution_type_id').val();

         $.getJSON('/standards_and_solutions/get_constituents/', {
            solution_type: solution_type,
            }, function(data) {
                var options = '';
                for (var item of data.choices) {
                    options += '<option value="' + item.id + '">' + item.name + '</option>';
                }

                console.log(options)

                $('#name').html(options)
                $('#name').selectpicker('refresh')
                $('#name').selectpicker('render')
                $('#name').selectpicker('val', 0)

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

                $('#name').html(options)
                $('#name').selectpicker('refresh')
                $('#name').selectpicker('render')
                $('#name').selectpicker('val', 0)
                populateConstituentData(table, id);
            });
            return false;
    });

    // Function to fetch and populate data based on item data
    function populateConstituentData(table, id) {
        $.getJSON('/standards_and_solutions/get_constituent_data/', { table: table, id: id }, function(data) {
            console.log('IN FUNC')
            // Update the field with the name "constituent"
            console.log('DATA CONST', data.name);
            $('#name').val(data.name).selectpicker('refresh');
            console.log('NAME UPDATED');
        });
    }

    // Extract table and id from URL
    var pathArray = window.location.pathname.split('/');
    var table = pathArray[1]; // Assuming the table is the second segment
    var id = pathArray[2];    // Assuming the id is the third segment

    console.log('TABLE', table);
    console.log('ID', id);

});