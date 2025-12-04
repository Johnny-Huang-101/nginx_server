
$(document).ready(function () {
    // Get the number of comments and set the number of rows of the text field
    // to number of comments + 1
    comments = $('#evidence_comments').val().split("\n")
    n_comments = comments.length
    $('#evidence_comments').prop('rows', n_comments + 1)
})

$(function() {
  $('#section').on('change', function() {
    let section = $(this).val();
    $.getJSON('/evidence_comments/get_field_choices/', {
      section: section,
    }, function(data) {
      let field_options = '';
      for (var field of data.fields) {
        field_options += '<option value="' + field.id + '">' + field.name + '</option>';
      }
      $('#field').html(field_options);
      $('#field').selectpicker('refresh');
      $('#field').selectpicker('render');
      $("#other").prop('readonly', true);
      $("#other").val("");

      if (section == 0) {
        $('#field').attr('disabled', true);
        $('#field').selectpicker('val', 0);
        $('#issue').attr('disabled', true);
        $('#issue').selectpicker('val', 0);
      } else {
         $('#field').attr('disabled', false);
         $('#issue').attr('disabled', false);
      }
      $('#field').selectpicker('refresh');
      $('#issue').selectpicker('refresh');

    });
    return false;
  });
});


$(function() {
  $('#issue').on('change', function() {
    let issue = $('#issue option:selected').text();
     if (issue == '7 - Other') {
        $("#comment").prop('readonly', false);
     } else {
        $("#comment").prop('readonly', true)
        $("#comment").val("")
     }
  });
});



$(function() {
  $('#submit_comment').on('click', function() {
    //var comments = $('#section option:selected').toArray().map(item => item.text).join('; ');
    var section = $('#section').val();
    var field = $('#field').val();
    var issue = $('#issue').val();
    var comment = $('#comment');
    errors = 0
    if (section == 0) {
         errors += 1
         $('#section').parent().addClass("is-invalid");
         $('#section_invalid').html("Invalid choice!");
    }
    if (field == 0) {
         errors += 1
         $('#field').parent().addClass("is-invalid");
         $('#field_invalid').html("Invalid choice!");
    }
    if (issue == 0) {
     errors += 1
     $('#issue').parent().addClass("is-invalid");
     $('#issue_invalid').html("Invalid choice!");
    }

    console.log(comment.val())
    console.log(comment.prop('readonly'))
    if ((comment.val() == "") && (comment.prop('readonly') == false)) {
         errors += 1
         $('#comment').addClass("is-invalid");
         $('#comment_invalid').html("Invalid choice!");
    }

    if (errors == 0) {
        $.getJSON('/evidence_comments/generate_comment/', {
              section: section,
              field: field,
              issue: issue,
              comment: comment.val()
            }, function(data) {
               let text = data.text;
               if (!$('#evidence_comments').val().includes(text)) {
                   if ($('#evidence_comments').val() == "") {
                        $('#evidence_comments').val(text);
                    } else {
                        $('#evidence_comments').val($('#evidence_comments').val()+'\n'+text);
                    }

                    $('.modal-footer').after('<div class="mt-3 alert alert-success flash-alert" role="alert" align="center"><b>'+text+'</b> successfully added!</div')
    //                $('#success').addClass("mt-3 alert alert-success flash-alert")
    //                $('#success').attr('role', 'alert')
    //                $('#success').attr('align', 'center')
    //                $('#success').html("<b>"+text+"</b> successfully added!")
                    $(".flash-alert").delay(3000).fadeOut(500)
                    let rows = $('#evidence_comments').prop('rows') + 1
                    $('#evidence_comments').prop('rows', rows)
                }
            });
    }
  });
});


$(function() {
    $('#sort').on('click', function() {
        // Get the commments from the evidence_comments field
        var comment_text = $('#evidence_comments').val()

        // Send request to server to sort the comments
        $.getJSON('/evidence_comments/sort_comments/', {
            comment_text: comment_text,
        }, function(data) {
            $('#evidence_comments').val(data.comments)

        })
    })
})

$(function() {
    $('#undo').on('click', function() {
        if ($('#evidence_comments').val()) {
            var comments = $('#evidence_comments').val().split("\n").slice(0,-1).join("\n");
            console.log(comments)
            console.log('hello')
            $('#evidence_comments').val(comments);
            let rows = $('#evidence_comments').prop('rows') - 1
            $('#evidence_comments').prop('rows', rows)

        }
    });
});


 $(function() {
  $('#clear').on('click', function() {
     $('#evidence_comments').val("");
     $('#evidence_comments').prop('rows', 2)
     });
});
