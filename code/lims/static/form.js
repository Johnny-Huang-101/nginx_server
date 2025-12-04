

$(document).ready(function() {
    styleFormControls();
    revertFields();
    provideFeedbackOnSubmit();
});


function styleFormControls() {
//    var required_fields = '{{required_fields}}';
    console.log(required_fields)
    $.each($(".form-control, .form-check-input"), function() {
        var id = $(this).attr('id');
        var label = $('label[for=' + id + ']');
        var title = $(this).attr('tooltip-text');


        label.css("font-weight", "bold");
        label.attr('title', title);
        label.attr('data-toggle', 'tooltip');
        if (label.attr('title')) {
            label.addClass('t-tip');
        }

        if ($(this).attr('name') !== 'length') {
            if ($(this).prop('tagName') === 'SELECT') {
                $(this).selectpicker({
                    "liveSearch": true,
                    "selectedTextFormat": "count > 10",
                    "actionsBox": true,
                });
            }
        }

//        if ($(this).prop('tagName') == 'SELECT') {
//            // Set the title of the select field back to None Selected to prevent
//            // the display of the modification tooltip text in the field
//            $(this).prop('title', 'None Selected')
//            //$(this).next('.btn').selectpicker('title', "Nothing selected");
//            $(this).selectpicker('refresh')
//            $(this).selectpicker('render')
//        } else {
//            $(this).attr('title', "");
//        }

        if (pending_fields.includes(id)) {
           if ($(this).prop('disabled') == false) {
               var revert = '<a href="#" class="revert ml-2" name="'+id+'"><i class="fa-solid fa-rotate-left"></i></a>';
               label.after(revert)
           }
        }

        if (required_fields.includes(id)) {
            label.after('<span style="color:red">*</span>');
        }
    });

    $('[data-toggle="tooltip"]').tooltip({
        content: function() {
            return $(this).prop('title');
        }
    });
}

function revertFields() {
  $('.revert').on('click', function() {
    var name = $(this).attr('name');
    var val = $('#'+name).val();
    $.getJSON('/'+table_name+'/revert_changes', {
      item_id: item_id,
      field_name: name,
      field_value: val,
      field_type : $('#'+name).prop('tagName'),
      multiple: $('#'+name).prop('multiple')
    }, function(data) {
        $('#'+name).val(data.value);
        if ($('#'+name).prop('tagName') == 'SELECT'){
            $('#'+name).selectpicker('refresh');
            $('#'+name).selectpicker('render');
        }

    });
    return false;
  });
};


function provideFeedbackOnSubmit() {
    //var errors = errors;
    console.log('Errors: ', errors)
    $.each(errors, function(field, message) {
        // Find the form field with the corresponding ID
        var fieldElement = $('#' + field);
        if (fieldElement.closest('.bootstrap-select').length) {
            fieldElement = fieldElement.closest('.bootstrap-select')
        }
        // Check if the field is within an input group (see submitted_sample_amount in specimens\form.html)
        var inputGroup = fieldElement.parents('.input-group')
        var subFieldElement = fieldElement.siblings('.form-group')
        // Check if the field exists and is visible
        if (fieldElement.length && fieldElement.is(':visible')) {
            //If the the field is part of an input group, add the error message after the input group
            // otherwise add the error message after the form field.
            // Add 'is-invalid' class to highlight the field with error
            var errorMessage = $('<div class="invalid-feedback">' + message + '</div>');
            if (inputGroup.length) {
                inputGroup.after(errorMessage)
                inputGroup.addClass('is-invalid')
            } else if (subFieldElement.length) {
                subFieldElement.after(errorMessage)
                subFieldElement.addClass('is-invalid')
            } else {
                fieldElement.after(errorMessage);
                fieldElement.addClass('is-invalid');
            }
        }
    });
}

$('#form').on('submit', function() {
    $.each($(".form-control"), function() {
        if ($(this).prop('disabled')) {
            $(this).prop('disabled', false);
        }
    });
    $('#submit').prop('disabled', true)
    $('#processing').modal('show');
});


$.each($('tbody td'), function () {
    if ($(this).text().trim() == "None") {
        $(this).text("")
    }
});
