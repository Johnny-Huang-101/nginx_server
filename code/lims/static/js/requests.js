$(document).ready(function() {
  // Initialize the selectpicker
  $('.selectpicker').selectpicker();

  // Event listener for changes in the selectpicker
  $('.selectpicker').on('changed.bs.select', function () {
    // Get the selected options
    var selectedOptions = $(this).val();
  });
});

  // adds text to header
  const heading = document.getElementById("{{table_name}}-header")
  heading.textContent += " | {{item.status}}"

  $(document).ready( function () {
 $('#divisions-table').DataTable({
     pageLength: -1,
     scrollX: true,
     scrollY: '50vh',
     scrollCollapse: true,
     lengthMenu: [[10, 50, 100, -1], [10, 50, 100, 'All']],
     order: [],
 });
});

 $(document).ready( function () {
 $('#personnel-table').DataTable({
     pageLength: -1,
     scrollX: true,
     scrollY: '50vh',
     scrollCollapse: true,
     lengthMenu: [[10, 50, 100, -1], [10, 50, 100, 'All']],
     order: [],
 });
});

 $(document).ready(function() {
// When the "specimen_review" modal is shown, select all options
$('#specimen_review').on('shown.bs.modal', function() {
    const selectField = $('[name="approved_specimens"]'); // More flexible selector
    selectField.find('option').prop('selected', true); // Select all options by default
    selectField.selectpicker('refresh'); // Refresh the UI for Bootstrap select
});
});

$(document).ready(function() {
// Function to disable form submission if no specimens are available
function checkSpecimenAvailability(formSelector, selectSelector) {
    const specimenSelect = $(selectSelector);
    const submitButton = $(formSelector).find('button[type="submit"]');
    const buttonDiv = $(formSelector).find('#button-div'); // Target `button-div` within the form

    if (specimenSelect.find('option').length === 1 && specimenSelect.find('option').val() === "") {
        // Disable the selectpicker and submit button if only the "No specimens found" option is present
        specimenSelect.prop('disabled', true);
        submitButton.prop('disabled', true);

        // Hide the button-div
        buttonDiv.hide(); // Hides the button container

    } else {
        specimenSelect.prop('disabled', false);
        submitButton.prop('disabled', false);

        // Show the button-div if options are present
        buttonDiv.show();
    }

    specimenSelect.selectpicker('refresh'); // Refresh selectpicker UI
}

// Apply the check with a slight delay when the modal shows
$('#specimen_add, #specimen_review').on('shown.bs.modal', function(event) {
    const formId = event.target.id;
    setTimeout(function() {
        if (formId === 'specimen_add') {
            checkSpecimenAvailability('#specimen_add_form', '#specimen_add_form select[name="specimens"]');
        } else if (formId === 'specimen_review') {
            checkSpecimenAvailability('#specimen_review_form', '#specimen_review_form select[name="approved_specimens"]');
        }
    }, 200); // Adjust the delay if necessary for your content load time
});
});