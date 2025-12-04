/* form.html */

// Get divisions for selected submitting agency
$('#submitting_agency').on('change', function (){
    $.getJSON('/cases/get_divisions/', {
        agency_id: $(this).val(),
        case_type_id: $('#case_type').val()
    }, function(data) {
        var optionHTML = '';
        for (var choice of data.divisions) {
            optionHTML += '<option value="' + choice.id + '">' + choice.name + '</option>';
        }
        $('#submitting_division').html(optionHTML);
        $('#submitting_division').selectpicker('refresh')
        $('#submitting_division').selectpicker('render')
        $('#submitting_division').selectpicker('val', data.default_client)
        console.log(data.default_client)

    });
    return false;
})


$('#date_of_birth, #date_of_incident').on('keyup change', function () {
    // if both date_of_birth and date_of_incident have data, make
    // the age field read-only. If date_of_birth has been fully entered,
    // i.e., the year value (first 4 characters) is 4 numbers (this restricts the number of times
    // the request is sent when someone is manually entering the date_of_birth),
    // calculate the age and display in the age field.
    let dob = $('#date_of_birth').val();
    let doi = $('#date_of_incident').val();
    if (dob != "" && doi != "") {
        $('#age').prop('readonly', true)
        console.log(Number(dob.slice(0,4)) >= 1000)
        if (Number(dob.slice(0,4)) > 1900) {
            $.getJSON('/cases/get_age/', {
                dob: dob,
                doi: doi,
                }, function(data) {
                   $('#age').val(data.age);
                });
                return false;
        }
    } else {
        $('#age').prop('readonly', false)
        $('#age').val("")
    }
})


function disableTestingRequested() {
 var checked = $('#no_testing_requested').prop('checked')
    if (checked) {
        $('#testing_requested').prop('disabled', true)
    } else {
        $('#testing_requested').prop('disabled', false)
    }

    $('#testing_requested').selectpicker('refresh')
}

$('#no_testing_requested').on('click', disableTestingRequested)
$(document).ready(disableTestingRequested)


$('#testing_requested').on('change', function () {
    var testing_requested = $('#testing_requested').val()
    console.log(testing_requested)
    if (testing_requested.length) {
        $('#no_testing_requested').prop('disabled', true)
    } else {
        $('#no_testing_requested').prop('disabled', false)
    }
})

// Disable the no_testing_requested field if testing_requested is blank and approved
$(document).ready(function () {
    if (['Edit', 'Approve'].includes(func)) {
        if (approved_fields.length && !pending_fields.includes('testing_requested') && !approved_fields.includes('testing_requested')) {
            $('#no_testing_requested').attr('disabled', true)
        }
    }
})

// Re-enable no_testing_requested on submit
$('#form').on('submit', function() {
    $('#no_testing_requested').attr('disabled', false)
});



/* list.html */

//$('.case-number').on('click', function (){
//    let pend = $(this).parents('tr').find('td.pending-submitter').html();
//    console.log('Pending submitter: ', pend)
//    let func = 'Review';
//    var case_number = $(this).attr('name')
//    var case_id = $(this).attr('value')
//
//    if (pend == '{{current_user.initials}}') {
//        func = 'Edit'
//    }
//    console.log(func);
//
//    $('.func_text').html(func);
//    $('.view-only').attr('href', "cases/"+case_id+"?view_only=True")
//    $('#proceed').attr('href', "cases/"+case_id)
//    $('.modal-case-number').html(case_number);
//
//    // Get disciplines of submitted evidence for the case
//    $.getJSON('/cases/get_case_evidence_disciplines/', {
//        case_id: case_id,
//        }, function(data) {
//            var HTML = '';
//            for (var choice of data.choices) {
//                HTML += '<option value="' + choice.id + '">' + choice.name + '</option>';
//            }
//        $('#discipline-select').html(HTML);
//    });
//
//    //Set default url for 'Review' button
//    $('#edit-review').attr('href', "cases/"+case_id)
//    $('#view-only').attr('href', "cases/"+case_id+"?view_only=True")
//    // Change the url of the Review button based on the discipline selection
//    $('#discipline-select').on('change', function () {
//        var discipline = $('#discipline-select').val()
//        if (discipline) {
//            $('#edit-review').attr('href', "cases/"+case_id+"?review_discipline="+discipline)
//        } else {
//            $('#edit-review').attr('href', "cases/"+case_id)
//        }
//    })
//});

//$(document).ready(function () {
//    $('#view_review').on('shown.bs.modal', function (event) {
//        // Optionally get the triggering element if available.
//        var trigger = event.relatedTarget;
//        // Try to get values from the trigger; if not available, assign defaults.
//        let pend = trigger ? $(trigger).parents('tr').find('td.pending-submitter').html() : '';
//        console.log('Pending submitter: ', pend);
//        let func = 'Review';
//        var case_number = trigger ? $(trigger).attr('name') : '';
//        var case_id = trigger ? $(trigger).attr('value') : '';
//
//
//        // If case_id is not found (falsy), use session['pending_case_id'].
//        if (!case_id) {
//            case_id = pendingCaseIdFromSession;
//        }
//
//        if (pend == '{{current_user.initials}}') {
//            func = 'Edit';
//        }
//        console.log(func);
//
//        $('.func_text').html(func);
//        $('.view-only').attr('href', "cases/" + case_id + "?view_only=True");
//        $('#proceed').attr('href', "cases/" + case_id);
//        $('.modal-case-number').html(case_number);
//
//        // Get disciplines of submitted evidence for the case
//        if (case_id) {
//            $.getJSON('/cases/get_case_evidence_disciplines/', { case_id: case_id }, function(data) {
//                var HTML = '';
//                for (var choice of data.choices) {
//                    HTML += '<option value="' + choice.id + '">' + choice.name + '</option>';
//                }
//                $('#discipline-select').html(HTML);
//            });
//        }
//
//        // Set default URL for 'Review' and 'View Only' buttons.
//        $('#edit-review').attr('href', "cases/" + case_id);
//        $('#view-only').attr('href', "cases/" + case_id + "?view_only=True");
//
//        // Change the URL of the Review button based on the discipline selection.
//        $('#discipline-select').on('change', function () {
//            var discipline = $('#discipline-select').val();
//            if (discipline) {
//                $('#edit-review').attr('href', "cases/" + case_id + "?review_discipline=" + discipline);
//            } else {
//                $('#edit-review').attr('href', "cases/" + case_id);
//            }
//        });
//    });
//});



// highlight row color based on status
$(document).ready(function () {
    $.each($('.datatable tbody tr'), function () {
        // Highlight rows based on status
        // Inactive, Obsolete = Grey (secondary)
        // Out of Service = Yellow (warning)
        // not-used = Red (danger)
        var status = $(this).find('td.case-status').text();
        console.log(status);
        if (status == 'Needs Accessioning' || status == 'Need Test Addition') {
            $(this).addClass('table-primary')
        }
    });
});

/* view.html */

$('.storage-type').on('change', function() {
   let storage_type = $(this).val()
   let storage_location = $(this).closest('.storage-location')
   console.log(storage_location.val())
//   $.getJSON('/cases/get_locations/', {
//            case_id: case_id,
//            }, function(data) {
//                var HTML = '';
//                for (var choice of data.choices) {
//                    HTML += '<option value="' + choice.id + '">' + choice.name + '</option>';
//                }
//                $('#division_id').html(HTML);
//                $('#division_id').selectpicker('val', 0);
//                $('#division_id').selectpicker('refresh');
//                $('#division_id').selectpicker('render');
//
//         });
//         return false;
//   });

})



