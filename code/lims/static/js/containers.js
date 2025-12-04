
$(function() {
      $('#case_id').on('change', function() {
        var case_id = $(this).val();
         $.getJSON('/containers/get_divisions/', {
            case_id: case_id,
            }, function(data) {
                var HTML = '';
                for (var choice of data.choices) {
                    HTML += '<option value="' + choice.id + '">' + choice.name + '</option>';
                }
                $('#division_id').html(HTML);
                $('#division_id').selectpicker('val', 0);
                $('#division_id').selectpicker('refresh');
                $('#division_id').selectpicker('render');

                $('#submitted_by').html('<option value="0">No division selected</option>')
                $('#submitted_by').selectpicker('val', 0);
                $('#submitted_by').selectpicker('refresh');
                $('#submitted_by').selectpicker('render');

         });
         return false;
      });
});



$(function() {
  $('#division_id').on('change', function() {
    var division_id = $(this).val()
    $.getJSON('/containers/get_personnel/', {
      division_id: division_id,
      }, function(data) {
       var optionHTML = '';
       for (var choice of data.choices) {
        optionHTML += '<option value="' + choice.id + '">' + choice.name + '</option>';
    }
        $('#submitted_by').html(optionHTML);
        console.log($('#submitted_by').html())
        $('#submitted_by').selectpicker('refresh')
        $('#submitted_by').selectpicker('val', 0);

    });
    return false;
  });
});

function handleSubmissionRouteTypeChange() {
    const selectedValue = $('#submission_route_type').val();

    if (selectedValue === 'By Location') {
        // Enable location-related fields
        $('#location_type').prop('disabled', false);
        $('#location_type').selectpicker('refresh');

        $('#submission_route').prop('disabled', false);
        $('#submission_route').selectpicker('refresh');

        // Hide transfer-related fields
        $('#transfer').css('display', 'none');
        $('#transfer_by').prop('disabled', true);

    } else if (selectedValue === 'By Transfer') {
        // Show transfer-related fields
        $('#transfer').css('display', 'block');
        $('#transfer_by').prop('disabled', false);
        $('#transfer_by').selectpicker('refresh');

        // Enable location-related fields
        $('#location_type').prop('disabled', false);
        $('#location_type').selectpicker('refresh');

        $('#submission_route').prop('disabled', false);
        $('#submission_route').selectpicker('refresh');

    } else {
        // For 'By Hand' or any other option, hide and disable transfer fields
        $('#transfer').css('display', 'none');
        $('#transfer_by').prop('disabled', true);

        // Disable and clear location-related fields
        $('#location_type').prop('disabled', true);
        $('#location_type').selectpicker('val', "");
        $('#location_type').selectpicker('refresh');

        $('#submission_route').prop('disabled', true);
        $('#submission_route').selectpicker('val', "");
        $('#submission_route').selectpicker('refresh');
    }
}

// Run the function on change
$('#submission_route_type').on('change', handleSubmissionRouteTypeChange);

// Run the function on page load
$(document).ready(function() {
    handleSubmissionRouteTypeChange();
});


$('#location_type').on('change', function() {
    var location_type = $(this).val()
//    if (location_type == 'Evidence Lockers') {
//        $('#locker-layout').attr('hidden', false)
//    } else {
//        $('#locker-layout').attr('hidden', true)
//    }
    $.getJSON('/containers/get_locations/', {
      location_type: location_type,
      }, function(data) {
       var optionHTML = '';
       for (var choice of data.choices) {
        optionHTML += '<option value="' + choice.id + '">' + choice.name + '</option>';
    }
        $('#submission_route').html(optionHTML);
        $('#submission_route').selectpicker('refresh')
        $('#submission_route').selectpicker('val', data.default_choice);

    });
    return false;
});


// If the personnel_id field is disabled on load i.e., the field has been approved, also
// disable the division_id field
// Disable future_submission_date if submission_date and submission_time are approved
$(document).ready(function () {

    if ($('#submitted_by').prop('disabled')) {
        $('#division_id').prop('disabled', true)
        $('#division_id').selectpicker('refresh')
    }

    if (approved_fields.includes('submission_date') && approved_fields.includes('submission_time')) {
        $('#future_submission_date').attr('disabled', true)
    }
})

// Re-enable future_submission_date on submit
$('#form').on('submit', function() {
    $('#future_submission_date').attr('disabled', false)
});

//  $(window).on('load', function() {
//    // Extract id from URL
//    var pathArray = window.location.pathname.split('/');
//    var id = pathArray[2];  // Assuming the id is the third segment
//    var division_id = $('#division_id').val();
//
//    // First, make the request to populate the submitted_by choices
//    $.getJSON('/containers/get_personnel/', {
//      division_id: division_id,
//    }, function(data) {
//      var optionHTML = '';
//      for (var choice of data.choices) {
//        optionHTML += '<option value="' + choice.id + '">' + choice.name + '</option>';
//      }
//
//      // Update the submitted_by field with the options
//      $('#submitted_by').html(optionHTML);
//      $('#submitted_by').selectpicker('refresh');
//
//      // After populating options, make the second request to set the selected value
//      $.getJSON('/containers/set_submitter/', {
//        id: id,
//      }, function(data) {
//        console.log('ID', data.selected_id);
//
//        // Now set the value of submitted_by to the id returned from the function
//        $('#submitted_by').selectpicker('val', data.selected_id);  // Set the correct selected value
//      });
//    });
//  });


//$(function() {
//    // Function to handle the location_type change and update the submission_route dropdown
//    function handleLocationTypeChange() {
//        var location_type = $('#location_type').val();
//
//        $.getJSON('/containers/get_locations/', {
//            location_type: location_type,
//        }, function(data) {
//            var options = '';
//            for (var item of data.choices) {
//                options += '<option value="' + item.id + '">' + item.name + '</option>';
//            }
//
//            // Update the submission_route dropdown
//            $('#submission_route').html(options);
//            $('#submission_route').selectpicker('refresh');
//            $('#submission_route').selectpicker('render');
//            $('#submission_route').selectpicker('val', " ");
//        });
//    }
//
//    // Event handler for submission_route_type change
//    function handleSubmissionRouteTypeChange() {
//        if ($('#submission_route_type').val() == 'By Location') {
//            $('#submission_route').prop('disabled', false);
//            $('#location_type').prop('disabled', false);
//            $('#submission_route').val(1);
//            $('#submission_route option:eq(0)').hide();
//            $('#submission_route').selectpicker('refresh');
//            $('#location_type').selectpicker('refresh');
//
//            // Run the location_type change logic if 'By Location' is selected
//            handleLocationTypeChange();
//        } else {
//            $('#submission_route').prop('disabled', true);
//            $('#location_type').prop('disabled', true);
//            $('#submission_route').val(0);
//            $('#submission_route option:eq(0)').show();
//            $('#submission_route').selectpicker('refresh');
//            $('#location_type').selectpicker('refresh');
//        }
//    }
//
//    // Bind the event handler to the submission_route_type change
//    $('#submission_route_type').on('change', handleSubmissionRouteTypeChange);
//
//    // Event handler for location_type change
//    $('#location_type').on('change', function() {
//        // Run the location_type change logic when location_type changes
//        handleLocationTypeChange();
//    });
//
//    // Trigger submission_route_type change on window load
//    $(document).ready(function() {
//        // Trigger submission_route_type change on window load
//        $('#submission_route_type').trigger('change');
//    });
//});

//Adding JS for Alias and MRN
$(document).ready(function () {
    $('.result-symbol').on('click', function () {
        let symbol = $(this).data('symbol'); // Get from data-symbol attribute
        symbol = symbol.replace(/\\n/g, '\n'); // Convert literal "\n" to actual line breaks
        let field = $('#notes'); // Replace with the actual ID of your text area
        let currentText = field.val();
        field.val(currentText + symbol);
        field.focus();//places the cursor back on the text field
    });
});

// Enable Observed By only when discipline is Drug
function handleObservedBy() {
  const $disc = $('#discipline');
  const $obs  = $('#observed_by');

  // Handle both value and visible text (covers int IDs vs text)
  const value = String($disc.val() ?? '').toLowerCase();
  const text  = ($disc.find('option:selected').text() || '').trim().toLowerCase();

  const isDrug = value === 'drug' || text.includes('drug');

  $obs.prop('disabled', !isDrug);

  if ($obs.data('selectpicker')) {
    $obs.selectpicker('refresh');
  }
}

// Run after the select(s) are initialized
$(function () {
  handleObservedBy();
  // Bind to both native change and bootstrap-select change (if you use it)
  $('#discipline')
    .on('change', handleObservedBy)
    .on('changed.bs.select', handleObservedBy);
});


