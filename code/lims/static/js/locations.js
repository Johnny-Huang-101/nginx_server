$(function() {
    // Function to update location_id based on location_table change
    $('#location_table').on('change', function() {
        var location_table = $('#location_table').val();

        $.getJSON('/locations/get_location_ids/', {
            location_table: location_table,
        }, function(data) {
            var options = '';
            for (var item of data.choices) {
                options += '<option value="' + item.id + '">' + item.name + '</option>';
            }

            $('#location_id').html(options);
            $('#location_id').selectpicker('refresh');
            $('#location_id').selectpicker('render');
            $('#location_id').selectpicker('val', " ");
        });
        return false;
    });

    // Function to fetch and populate location_type and location_id based on item data
    function populateLocationData(table, id) {
        $.getJSON('/locations/get_location_data/', { table: table, id: id }, function(data) {
            if (data.location_type && data.location_id) {
                console.log('LOCATION TYPE', data.location_type)
                // Find the option with the display name matching location_type
                var location_table_option = $('#location_table option').filter(function() {
                    return $(this).text() === data.location_type.replace(/_/g, ' ');
                }).val();

                // Set the value of location_table selectpicker
                $('#location_table').val(location_table_option).selectpicker('refresh');
                console.log('FIRST REQUEST COMPLETE');
                console.log(data.location_type)
                // Fetch location_id options based on location_table selection
                $.getJSON('/locations/get_location_ids/', {
                    location_table: location_table_option,
                }, function(idData) {
                    console.log('SECOND REQUEST START');
                    var options = '';
                    for (var item of idData.choices) {
                        options += '<option value="' + item.id + '">' + item.name + '</option>';
                    }
                    console.log('TEST 3')
                    $('#location_id').html(options);
                    $('#location_id').selectpicker('refresh');
                    $('#location_id').selectpicker('render');
                    // Set the value of location_id selectpicker with data.location_id
                    $('#location_id').val(data.location_id).selectpicker('refresh');
                });
            }
        });
    }

    // Extract table and id from URL
    var pathArray = window.location.pathname.split('/');
    var table = pathArray[1]; // Assuming the table is the second segment
    var id = pathArray[2];    // Assuming the id is the third segment

    console.log('TABLE', table);
    console.log('ID', id);

    // Call the populate function on page load
    populateLocationData(table, id);

});

