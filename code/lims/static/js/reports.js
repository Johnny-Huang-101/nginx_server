$(document).ready(function() {
    var report_type = $('#report_type').val()
      if (report_type == 'Manual Upload') {
        $('#file-upload').attr('hidden', false);
        $('#record-template').attr('hidden', true);
      } else {
        $('#file-upload').attr('hidden', true);
        $('#record-template').attr('hidden', false);
      }
    $.each($('tbody tr'), function () {
       var report_as = $(this).find('td').eq(1).find('select').val()
       if (report_as == 'Official') {
            $(this).css('font-weight', 'bold');
       }
       var result_status = $(this).find('td').eq(3).text()
       console.log(result_status);
       if (result_status == 'Confirmed') {
           $(this).addClass('table-active')
       } else if(result_status == 'Saturated') {
        $(this).addClass('table-active')
       } else if(result_status == 'Not Tested') {
        $(this).addClass('table-active')
       }
    });
});

// If the report type is "Manual Upload", hide the "Report Template"
// field and show the File Upload field.
$('#report_type').on('change', function () {
  var report_type = $(this).val()
  if (report_type == 'Manual Upload') {
    $('#file-upload').attr('hidden', false);
    $('#record-template').attr('hidden', true);
    $('#results-div').attr('hidden', true);
  } else {
    $('#file-upload').attr('hidden', true);
    $('#record-template').attr('hidden', false);
    $('#results-div').attr('hidden', false);
  }
});

// When the case_id is changed, populate the discipline field
// with the relevant disciplines for the case
$('#case_id').on('change', function() {
    var case_id = $(this).val();
    $('#results-div').attr('hidden', true);
    $.getJSON('/reports/get_disciplines/', {
      case_id: $(this).val(),
    }, function(data) {

   // Update discipline choices
   var optionHTML = '';
   for (var choice of data.choices) {
        optionHTML += '<option value="' + choice.id + '">' + choice.name + '</option>';
    }

    $('#discipline').html(optionHTML);
    $('#discipline').selectpicker('refresh');
    $('#discipline').selectpicker('render');

    // Clear result fields.
    $('#result_id_order').val("")
    $('#result_id').selectpicker('val', "")
    $('#primary_result_id').selectpicker('val', "")
    $('#supplementary_result_id').selectpicker('val', "")
    $('#observed_result_id').selectpicker('val', "")
    $('#qualitative_result_id').selectpicker('val', "")
    $('#approximate_result_id').selectpicker('val', "")

    return false;
  });
});

// If the discipline or result status filter changes, refresh
// the form updating the results available for selection.
// A discipline has to be selected for the request to be sent.
$('#discipline, #result_status_filter').on('change', function() {
        var case_id = $('#case_id').val();
        var discipline = $('#discipline').val();
        var result_statuses = $('#result_status_filter').val();
        $('#results-div').attr('hidden', true);
        if (discipline != 0) {
            if ($('#report_type').val() == 'Auto-generated') {
                // Show the fetching-results modal
                $('#fetching-results').modal('show');
                window.location.href = '/reports/add?item_id='+case_id+'&discipline='+discipline+'&result_statuses='+result_statuses
            }
        } else {
            // If the user sets the discipline back to "Please select a discipline"
            // and a case is selected, refresh the page parsing in the case_id.
            window.location.href = '/reports/add?item_id='+case_id
        }
  });

// Select all results for a specimen
$('.select-all').on('click', function() {
    var rows = $(this).parent().next('table').find('tbody').find('tr')
    let result_ids = $('#result_id').val().map(Number);
    let primary_result_ids = $('#primary_result_id').val().map(Number);
    let supplementary_result_ids = $('#supplementary_result_id').val().map(Number);
    var component = ""
    $.each(rows, function() {
        $(this).addClass('table-active');
        var result_id = Number($(this).find('td').eq(-1).text());
        console.log(result_id);
        result_ids.push(result_id);
        var component_name = $(this).find('td').eq(4).text();
        var supplementary_result = $(this).find('td').eq(6).text();
        var supplementary_checkbox = $(this).find('td').eq(2).find('.supplementary');
        if (component != component_name) {
            component = component_name
            $(this).find('td').eq(1).find('select').val('Official');
            primary_result_ids.push(result_id);
            $(this).css('font-weight', 'bold');
            if (supplementary_result) {
                supplementary_checkbox.prop('checked', true);
                supplementary_result_ids.push(result_id);
            }
        }
    });
    result_ids = result_ids.concat($('#result_id').val())
    $('#result_id').selectpicker('val', result_ids)
    $('#primary_result_id').selectpicker('val', primary_result_ids)
    $('#supplementary_result_id').selectpicker('val', supplementary_result_ids)

});

// Unselect all results for a specimen
$('.clear').on('click', function() {
    var rows = $(this).parent().next('table').find('tbody').find('tr')
    let result_ids = $('#result_id').val().map(Number);
    let primary_result_ids = $('#primary_result_id').val().map(Number);
    let supplementary_result_ids = $('#supplementary_result_id').val().map(Number);
    let observed_result_ids = $('#observed_result_id').val().map(Number);
    let qualitative_result_ids = $('#qualitative_result_id').val().map(Number);
    let approximate_result_ids = $('#approximate_result_id').val().map(Number);

    console.log(supplementary_result_ids);

    $.each(rows , function() {
        var result_id = Number($(this).find('td').eq(-1).text())
        result_idx = result_ids.indexOf(result_id)
        result_ids.splice(result_idx, 1)

        primary_idx = primary_result_ids.indexOf(result_id)
        if (primary_idx != -1) {
         primary_result_ids.splice(primary_idx, 1)
        }

        supplementary_idx = supplementary_result_ids.indexOf(result_id)
        if (supplementary_idx != -1) {
         supplementary_result_ids.splice(supplementary_idx, 1)
        }

        observed_idx = observed_result_ids.indexOf(result_id)
        if (observed_idx != -1) {
         observed_result_ids.splice(observed_idx, 1)
        }

        qualitative_idx = qualitative_result_ids.indexOf(result_id)
        if (qualitative_idx != -1) {
         qualitative_result_ids.splice(qualitative_idx, 1)
        }

        approximate_idx = approximate_result_ids.indexOf(result_id)
        if(approximate_idx != -1) {
            approximate_result_ids.splice(approximate_idx, 1)
        }

        $(this).removeClass('table-active');
        $(this).find('td').eq(1).find('select').val('');
        $(this).find('td').eq(2).find('.supplementary').prop('checked', false);
        $(this).css('font-weight', 'normal')
    });

    $('.primary').prop('checked', false);
    $('.primary').prop('disabled', false);
    $('#result_id').selectpicker('val', result_ids)
    $('#primary_result_id').selectpicker('val', primary_result_ids)
    $('#supplementary_result_id').selectpicker('val', supplementary_result_ids)
    $('#observed_result_id').selectpicker('val', observed_result_ids)
    $('#qualitative_result_id').selectpicker('val', qualitative_result_ids)
    $('#approximate_result_id').selectpicker('val', approximate_result_ids)

});

// Check all Inc. Suppl. for a specimen
$('.all-supplementary').on('click', function () {
    var rows = $(this).parent().next('table').find('tbody').find('.supplementary')
    let supplementary_result_ids = $('#supplementary_result_id').val().map(Number);
    $.each(rows, function() {
        $(this).prop('checked', true)
        var result_id = Number($(this).parents('tr').find('td').eq(-1).text());
        if (!supplementary_result_ids.includes(result_id) ) {
            supplementary_result_ids.push(result_id, 1)
        }
    });

    $('#supplementary_result_id').selectpicker('val', supplementary_result_ids)

});

// Uncheck/clear all Inc. Suppl. for a specimen
$('.clear-supplementary').on('click', function () {

    var rows = $(this).parent().next('table').find('tbody').find('.supplementary')
    let supplementary_result_ids = $('#supplementary_result_id').val().map(Number);
    $.each(rows, function() {
        $(this).prop('checked', false);
        var result_id = Number($(this).parents('tr').find('td').eq(-1).text());
        if (supplementary_result_ids.includes(result_id) ) {
            let result_idx = supplementary_result_ids.indexOf(result_id)
            console.log(result_idx)
            supplementary_result_ids.splice(result_idx, 1)
        }
    });
    $('#supplementary_result_id').selectpicker('val', supplementary_result_ids)

});

// Handle row highlighting/unlighting on row click.
$('table').on('click', 'td', function () {
    if ($(this).hasClass('clicking')) {
        // Get the current row
        var row = $(this).parent()
        //Initialise values
        var result_id = Number(row.find('td').eq(-1).text())
        var component_name = row.find('td').eq(4).text()
        var results = $('#result_id').val().map(Number)
        var results_order = $('#result_id_order').val().split(', ').map(Number);
        var primary_results = $('#primary_result_id').val().map(Number)
        var supplementary_results = $('#supplementary_result_id').val().map(Number)
        var observed_results = $('#observed_result_id').val().map(Number)
        var qualitative_results = $('#qualitative_result_id').val().map(Number)
        var approximate_results = $('#approximate_result_id').val().map(Number)

        // If the result is already selected,
        // and bold font. Set the select field
        if (row.hasClass('table-active')) {
            // remove green higlighting
            row.removeClass('table-active');
            // remove bold font
            row.css('font-weight', 'normal');
            // set the select field to nothing
            row.find('td').eq(1).find('select').val("");
            // Uncheck and disable supplementary r
            row.find('td').eq(2).find('.supplementary').prop({
                'checked': false, 'disabled': true
            });

            //row.find('td').eq(2).find('.supplementary')
            //row.find('td').eq(1).find('select').prop('disabled', true);
            var idx = results.indexOf(result_id);
            results.splice(idx,1)
            var prim_idx = primary_results.indexOf(result_id)
            //console.log(prim_idx);
            if (prim_idx != -1) {
                primary_results.splice(prim_idx,1)
                $(this).css('font-weight', 'normal');
                var rows = $(this).parents('tbody').find('.table-active')
                $.each(rows, function () {
                    if ($(this).find('td').eq(4).text() == component_name) {
                        primary_results.push($(this).find('td').eq(-1).text());
                        $(this).find('td').eq(1).find('select').val("Official");
                        supplementary_results.push($(this).find('td').eq(-1).text())
                        $(this).find('td').eq(2).find('.supplementary').prop("checked", true);
                        $(this).find('td').eq(2).find('.supplementary').prop("disabled", false);
                        //console.log($(this).prop('tagName'));
                        $(this).css('font-weight', 'bold');
                    }
                });

            }

            //console.log(result_id);
            var order_idx = results_order.indexOf(result_id);
            //console.log(order_idx)
            if (order_idx != -1) {
                results_order.splice(order_idx, 1)
            }
            //console.log(results_order);
            var supp_idx = supplementary_results.indexOf(result_id)
            //console.log(supp_idx);
            if (supp_idx != -1) {
                supplementary_results.splice(supp_idx,1)
            }

            var obs_idx = observed_results.indexOf(result_id)
            //console.log(prim_idx);
            if (obs_idx != -1) {
                observed_results.splice(obs_idx,1)
            }

            var qual_idx = qualitative_results.indexOf(result_id)
            //console.log(qual_idx);
            if (qual_idx != -1) {
                qualitative_results.splice(qual_idx,1)
            }

        } else {

            next_id = Number(row.nextAll('.table-active').eq(0).find('td').eq(-1).text())
            console.log(next_id);
            if (next_id) {
                order_idx = results_order.indexOf(next_id)
                results_order.splice(order_idx, 0, result_id)
                console.log(order_idx)
            } else {
                results_order.push(result_id);
            }

            var rows = $(this).parents('tbody').find('.table-active')
            $(this).parent().find('td').eq(1).find('select').prop("disabled", false);
            component_names = []
            $.each(rows, function () {
                component_names.push($(this).find('td').eq(4).text())
            });



            if (!component_names.includes(component_name)) {
                primary_results.push($(this).parent().find('td').eq(-1).text());
                supplementary_results.push($(this).parent().find('td').eq(-1).text());

                $(this).parent().find('td').eq(1).find('select').val("Official");
                $(this).parent().find('td').eq(2).find('.supplementary').prop("checked", true);
                $(this).parent().find('td').eq(2).find('.supplementary').prop("disabled", false);
                $(this).parent().css('font-weight', 'bold');
                //console.log(supplementary_results);
            } else {
                $(this).parent().find('td').eq(2).find('.supplementary').prop("disabled", true);
            }

            row.addClass('table-active');
            results.push(result_id)
        }

        $('#result_id_order').val(results_order.join(", "));
        $('#result_id').selectpicker('val', results)
        $('#primary_result_id').selectpicker('val', primary_results)
        $('#supplementary_result_id').selectpicker('val', supplementary_results)
        $('#observed_result_id').selectpicker('val', observed_results)
        $('#qualitative_result_id').selectpicker('val', qualitative_results)
        $('#approximate_result_id').selectpicker('val', approximate_results)
    }
})



// Handle the checking/unchecking of "Inc. Suppl." checkbox
$('.supplementary').on('click', function () {
    let row = $(this).closest('tr')
    let supplementary_result_ids = $('#supplementary_result_id').val().map(Number);
    let result_ids = $('#result_id').val().map(Number);
    let result_id = Number(row.find('td').eq(-1).text())

    if (!row.hasClass('table-active')) {
        row.addClass('table-active');
        result_ids.push(result_id);
        supplementary_result_ids.push(result_id);
    } else {
        if ($(this).prop('checked') == false) {
            console.log('Unchecked');
            supplementary_idx = supplementary_result_ids.indexOf(result_id);
            supplementary_result_ids.splice(supplementary_idx, 1);
        } else {
            console.log('Checked');
            supplementary_result_ids.push(result_id);
        }
    }

    console.log(supplementary_result_ids);
    $('#result_id').selectpicker('val', result_ids)
    $('#supplementary_result_id').selectpicker('val', supplementary_result_ids)
});

// // Move the result down in the order
// $('.move-down').on('click', function () {
//     var row = $(this).parents('tr')
//     var row_idx = row.index() + 1 // Have to add +1 because eq() is not zero-indexed
//     var result_id = Number(row.find('td').eq(-1).text());
//     var next_result_id = Number($(this).parents('table').find('tr').eq(row_idx+1).find('td').eq(-1).text());
//     var last_result_id = Number($(this).parents('table').find('tr').eq(-1).find('td').eq(-1).text());
//     var results_order = $('#result_id_order').val().split(", ").map(Number)
//     var idx = results_order.indexOf(result_id)
//     var last_result_idx = results_order.indexOf(last_result_id)

//     if (idx != last_result_idx) {
//         if (results_order.includes(next_result_id)) {
//             results_order.splice(idx, 1)
//             results_order.splice(idx+1, 0, result_id)
//         }
//         row.next().after(row);

//         var x = 1
//         $.each($(this).parents('tbody').find('tr'), function () {
//          $(this).find('td').eq(0).text(x);
//          x++
//         });

//         $('#result_id_order').val(results_order.join(", "))
//     }

// })

// // Move the result up in the order
// $('.move-up').on('click', function () {
//     var row = $(this).parents('tr')
//     var row_idx = row.index() + 1 // Have to add +1 because eq() is not zero-indexed
//     var result_id = Number(row.find('td').eq(-1).text());
//     var first_result_id = Number($(this).parents('table').find('tr').eq(1).find('td').eq(-1).text());
//     var prev_result_id = Number($(this).parents('table').find('tr').eq(row_idx-1).find('td').eq(-1).text());
//     var results_order = $('#result_id_order').val().split(", ").map(Number)
//     var idx = results_order.indexOf(result_id)
//     var first_row_idx = results_order.indexOf(first_result_id)

//     if (idx != first_row_idx) {
//         if (results_order.includes(prev_result_id)) {
//             results_order.splice(idx, 1)
//             results_order.splice(idx-1, 0, result_id)
//         }
//         row.prev().before(row);

//         var x = 1
//         $.each($(this).parents('tbody').find('tr'), function () {
//          $(this).find('td').eq(0).text(x);
//          x++
//         });

//         $('#result_id_order').val(results_order.join(", "))

//     }
// })


$('.reported-as').on('change', function () {
    var selection = $(this).val()
    var result_id = Number($(this).parents('tr').find('td').eq(-1).text())
    var row = $(this).parents('tr')
    var supplementary_checkbox = $(this).parents('tr').find('td').eq(2).find('.supplementary');
    console.log(supplementary_checkbox);
    var official_results = $('#primary_result_id').val().map(Number)
    var observed_results = $('#observed_result_id').val().map(Number)
    var qualitative_results = $('#qualitative_result_id').val().map(Number)
    var supplementary_results = $('#supplementary_result_id').val().map(Number)
    var approximate_results = $('#approximate_result_id').val().map(Number)

    // Check if result is selected in any of official_results, observed_results,
    // qualitative_results or supplementary results and remove it as a selected option.

    official_idx = official_results.indexOf(result_id)
    if (official_idx != -1) {
     official_results.splice(official_idx, 1)
    }

    observed_idx = observed_results.indexOf(result_id)
    if (observed_idx != -1) {
     observed_results.splice(observed_idx, 1)
    }

    qualitative_idx = qualitative_results.indexOf(result_id)
    if (qualitative_idx != -1) {
     qualitative_results.splice(qualitative_idx, 1)
    }

    approximate_idx = approximate_results.indexOf(result_id)
    if(approximate_idx != -1) {
        approximate_results.splice(approximate_idx, 1)
    }

    //supplementary_idx = supplementary_results.indexOf(result_id)
    //if (supplementary_idx != -1) {
    // supplementary_results.splice(supplementary_idx, 1)
    //}


    // if selection is '' or 'Observed' set the font-weight to normal
    // else bold the row
    if (['', 'Observed'].includes(selection)) {
        console.log("nothing or observed");
        row.css('font-weight', 'normal');
    } else {
        console.log("official");
        row.css('font-weight', 'bold');
    }

    // if 'Official' is selected, re-enabled checkbox and check it
    // else uncheck and disable
    //if (selection == 'Official') {
    //    supplementary_checkbox.prop('disabled', false);
    //     supplementary_checkbox.prop('checked', true);
    //    if (supplementary_checkbox.length) {
    //        supplementary_results.push(result_id)
    //    }
    //} else {
    //    supplementary_checkbox.prop('disabled', true);
    //    supplementary_checkbox.prop('checked', false);
    //}

    // Push result to appropriate array and update selectpickers
    if (selection == 'Official') {
        official_results.push(result_id)
    } else if (selection == 'Official (Qualitative)') {
        qualitative_results.push(result_id)
    } else if (selection == 'Observed') {
        observed_results.push(result_id)
    } else if (selection == 'Approximate') {
        approximate_results.push(result_id)
    }

    $('#primary_result_id').selectpicker('val', official_results)
    $('#qualitative_result_id').selectpicker('val', qualitative_results)
    $('#observed_result_id').selectpicker('val', observed_results)
    $('#supplementary_result_id').selectpicker('val', supplementary_results)
    $('#approximate_result_id').selectpicker('val', approximate_results)

});

$(document).ready(function() {
    console.log("🚀 Initializing 'Official' results on page load...");

    let official_results = [];
    let observed_results = [];
    let qualitative_results = [];
    let supplementary_results = [];
    let approximate_results = []

    $("tbody tr").each(function () {
        let result_id = Number($(this).find("td").last().text().trim());  // Get result ID from last column
        let selection = $(this).find(".reported-as").val();  // Get dropdown value

        if (selection === "Official") {
            official_results.push(result_id);
            $(this).css("font-weight", "bold");  // Make it bold
        } else if (selection === "Official (Qualitative)") {
            qualitative_results.push(result_id);
        } else if (selection === "Observed") {
            observed_results.push(result_id);
        } else if (selection === "Approximate") {
            approximate_results.push(result_id)
        }

        let supplementary_checkbox = $(this).find(".supplementary");
        if (supplementary_checkbox.is(":checked")) {
            supplementary_results.push(result_id);
        }
    });

    console.log("✅ Initial Official Results:", official_results);
    console.log("✅ Initial Observed Results:", observed_results);
    console.log("✅ Initial Qualitative Results:", qualitative_results);
    console.log("✅ Initial Supplementary Results:", supplementary_results);

    // Set initial values in form fields
    $('#primary_result_id').selectpicker('val', official_results);
    $('#qualitative_result_id').selectpicker('val', qualitative_results);
    $('#observed_result_id').selectpicker('val', observed_results);
    $('#supplementary_result_id').selectpicker('val', supplementary_results);
    $('#approximate_result_id').selectpicker('val', approximate_results);
});


$(document).ready(function () {
    
    function updateOrderField() {
        let resultOrder = [];
        $("tbody tr").each(function () {
            let resultId = $(this).find("td:last").text().trim(); // Assuming result ID is in the last column
            if (resultId && !isNaN(resultId)) {
                resultOrder.push(resultId);
            }
        });

        $("#result_id_order").val(resultOrder.join(", ")); // Update hidden input
    }

    function updateDropdowns() {
        $("tbody").each(function () { // Ensure we only loop per table
            let allRows = $(this).find("tr:not(:has(th))"); // Exclude headers and specimen rows
            allRows.each(function (index) {
                let $dropdown = $(this).find(".order-select");
                let selectedValue = index + 1;
                let optionsHtml = "";

                for (let i = 1; i <= allRows.length; i++) {
                    optionsHtml += `<option value="${i}" ${i === selectedValue ? "selected" : ""}>${i}</option>`;
                }

                $dropdown.html(optionsHtml);
            });
        });
        updateOrderField();
    }

    $(".order-select").change(function () {
        let newIndex = parseInt($(this).val(), 10) - 1;
        let row = $(this).closest("tr");
        let allRows = row.closest("tbody").find("tr:not(:has(th))");

        if (newIndex >= 0 && newIndex < allRows.length) {
            let targetRow = allRows.eq(newIndex);
            if (row.index() < newIndex) {
                row.insertAfter(targetRow);
            } else {
                row.insertBefore(targetRow);
            }
            updateDropdowns();
        }
    });

    $(".move-up").click(function () {
        let row = $(this).closest("tr");
        if (row.prev().length) {
            row.insertBefore(row.prev());
            updateDropdowns();
        }
    });

    $(".move-down").click(function () {
        let row = $(this).closest("tr");
        if (row.next().length) {
            row.insertAfter(row.next());
            updateDropdowns();
        }
    });

    updateDropdowns(); // Ensure it initializes properly

    // check if result has supplementary - if not, disable check box 
    $(".supplementary").each(function() {
        if (!$(this).closest("tr").find("td").eq(6).text().trim()){
            $(this).hide()
        } 
    })

    console.log("======= FORM DATA AT LOAD =======");

    $("tbody tr").each(function (index) {
        let row = $(this);
        let resultId = row.find("td:last").text().trim(); // Assuming Result ID is in the last column
        let resultStatus = row.find("td").eq(3).text().trim(); // Status column (Confirmed, etc.)
        let reportAs = row.find("td").eq(1).find("select").val(); // Reported As dropdown
        let supplementaryChecked = row.find("td").eq(2).find(".supplementary").prop("checked"); // Checkbox state

        console.log(`Row ${index + 1}: 
            Result ID: ${resultId}, 
            Status: ${resultStatus}, 
            Reported As: ${reportAs}, 
            Supplementary Checked: ${supplementaryChecked}`);
    });

    console.log("===================================");
    $("#update-form").submit(function(event) {
        event.preventDefault();  // Prevent default submission to log first
        let formData = $(this).serializeArray();
        console.log("FORM DATA SENDING:", formData);
        $(this).off('submit').submit();  // Re-enable submission
    });
    
});

