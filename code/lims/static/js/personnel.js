// Wait until document is ready
$(document).ready(function() {
    // Populate division based on agency selection change
    $('#agency_id').on('change', function() {
        const agency_id = $(this).val();
        populateDivisionDropdown(agency_id);
    });

    // Function to populate division dropdown based on agency
    function populateDivisionDropdown(agency_id) {
        const divisionSelect = $('#division_id');
        $.getJSON('/personnel/get_divisions/', { agency_id: agency_id }, function(data) {
            let options = '';
            data.divisions.forEach(division => {
                options += `<option value="${division.id}">${division.name}</option>`;
            });
            divisionSelect.html(options).selectpicker('refresh');
            divisionSelect.selectpicker('render');
        });
    }

    // Pre-populate agency and division if available in URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    const agencyId = urlParams.get("agency_id");
    const divisionId = urlParams.get("division_id");

    if (agencyId) {
        $('#agency_id').val(agencyId).prop('disabled', true).trigger('change');

        // After agency is set, populate division and set it to the correct value
        populateDivisionDropdown(agencyId); // Populate dropdown with divisions

        // Wait briefly to ensure divisions are loaded, then set division value
        setTimeout(() => {
            $('#division_id').val(divisionId).prop('disabled', true).selectpicker('refresh');
        }, 500); // Adjust timeout as needed for data loading
    }
});
