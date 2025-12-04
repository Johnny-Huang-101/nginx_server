$(function() {
    function updateConstituentType() {
        let solution_type = $('#solution_type').val();

        $.getJSON('/sequence_constituents/get_constituents/', {
            solution_type: solution_type
        }, function(data) {
            let options = '';
            for (let item of data.choices) {
                options += '<option value="' + item.id + '">' + item.name + '</option>';
            }

            console.log(options);

            $('#constituent_type').html(options);
            $('#constituent_type').selectpicker('refresh');
            $('#constituent_type').selectpicker('render');
            $('#constituent_type').selectpicker('val', 0);
        });
    }

    // Run on page load
    updateConstituentType();

    // Run on change
    $('#solution_type').on('change', function() {
        updateConstituentType();
    });
});
