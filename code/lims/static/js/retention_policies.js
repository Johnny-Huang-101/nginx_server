 // if date selection is manual, make retention length readonly and clear any text

$(document).ready(function () {
    if ($('#date_selection').val() == 'Manual') {
        $('#retention_length').prop('disabled', true);
    } else {
        $('#retention_length').prop('disabled', false);
    }
})

$('#date_selection').on('change', function () {
    if ($(this).val() == 'Manual') {
        $('#retention_length').val("");
        $('#retention_length').prop('disabled', true);
    } else {
        $('#retention_length').prop('disabled', false);
    }
})


// if one_year is clicked, set retention length to 36500 days (i.e., 100 years)
  $('#one_year').on('click', function() {
     if ($('#date_selection').val() == 'Automatic') {
        $('#retention_length').val(365);
     }
  });


 // if five_year is clicked, set retention length to 1825 days.

  $('#five_year').on('click', function() {
    if ($('#date_selection').val() == 'Automatic') {
        $('#retention_length').val(1825);
     }
  });


// if indefinite is clicked, set retention length to 36500 days (i.e., 100 years).

  $('#indefinite').on('click', function() {
     if ($('#date_selection').val() == 'Automatic') {
        $('#retention_length').val(36500);
     }
  });

