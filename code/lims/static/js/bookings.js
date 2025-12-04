$(document).ready(function () {
    const elementsToToggle = '#cross_examined, #personnelB1_id, #personnelB2_id, #drive_time, #excluded_time, #waiting_time';
    const formatField = $('#format_id');
    const locationField = $('#location');
    const purposeField = $('#purpose_id');

    const disableElements = () => $(elementsToToggle).prop('disabled', true).selectpicker('refresh');
    const enableElements = () => $(elementsToToggle).prop('disabled', false).selectpicker('refresh');

    const resetValues = () => {
      const pad = n => (n < 10 ? '0' + n : n);
      const d   = new Date();
      const ymd = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

      if (!formatField.val()) {
          formatField.val('').change().selectpicker('refresh');
      }
      if (!locationField.val()) {
          locationField.val('').change().selectpicker('refresh');
      }
      if (!$('#start_datetime').val()) {
          $('#start_datetime').val(`${ymd}T00:00`).trigger('change');
      }
      if (!$('#finish_datetime').val()) {
          $('#finish_datetime').val('').trigger('change');
      }
  };

    const handleFormatChange = () => {
        const formatId = formatField.val();
        const isInPerson = formatId == '1';
        locationField.prop('disabled', !isInPerson).selectpicker('refresh');
        $('#drive_time').prop('disabled', !isInPerson).selectpicker('refresh');
    };

  const handlePurposeChange = () => {
      const purposeId = purposeField.val();

      // helper: returns "YYYY-MM-DDTHH:MM" for today at given hour/minute
      const todayAt = (hh, mm) => {
          const d = new Date();
          const pad = n => (n < 10 ? '0' + n : n);
          return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(hh)}:${pad(mm)}`;
      };

      if (purposeId === '8') {                              //purpose: subpoena
          if (formatField.val() !== '4') {
              formatField.val('4').change().selectpicker('refresh'); //purpose: email
          }
          disableElements();
          // ---- set start / finish with today's date + deafult times: 00:00 ----
          $('#start_datetime').val(todayAt(0, 0)).trigger('change');
          $('#finish_datetime').val(todayAt(0, 15)).trigger('change');

        } else if (purposeId === '10' || purposeId === '11') {   //purpose: expert written opinion
            if (formatField.val() !== '5') {
                formatField.val('5').change().selectpicker('refresh');   // N/A
            }
            disableElements();

            const pad = n => (n < 10 ? '0' + n : n);
            const d   = new Date();
            const ymd = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

            // ---- set start / finish with today's date + deafult times: 9:00-9:15(expert opinion), 9:15-9:30(reviewer) ----
            $('#start_datetime')
                .val(purposeId === '10'
                    ? `${ymd}T09:00`
                    : `${ymd}T09:15`)
                .trigger('change');

            $('#finish_datetime')
                .val(purposeId === '10'
                    ? `${ymd}T09:15`
                    : `${ymd}T09:30`)
                .trigger('change');
      } else {
          resetValues();
          enableElements();
      }
  };

    formatField.on('change', handleFormatChange);
    purposeField.on('change', handlePurposeChange);

    // Initialize based on current values
    handleFormatChange();
    handlePurposeChange();

    // Trigger changes to populate fields on page load (for update forms)
    $('#agency_id').trigger('change');
    $('#cross_examined').trigger('change');
});


// Populate the personnel_id dropdown based on agency_id selection
$('#agency_id').on('change', function() {
    var agency_id = $(this).val();
    $.getJSON('/bookings/get_personnel/', {
      agency_id: agency_id,
    }, function(data) {
       var choices = '';
       for (var choice of data.choices) {
        choices += '<option value="' + choice.id + '">' + choice.name + '</option>';
       }
        $('#personnel_id, #personnelA2_id').each(function() {
            $(this).html(choices);
            $(this).selectpicker('refresh');
            $(this).selectpicker('render');
        });
    });
    return false;
});

$('#cross_examined').on('change', function() {
    var agency_id = $(this).val();
    $.getJSON('/bookings/get_personnel/', {
      agency_id: agency_id,
    }, function(data) {
       var choices = '';
       for (var choice of data.choices) {
        choices += '<option value="' + choice.id + '">' + choice.name + '</option>';
       }
        $('#personnelB1_id, #personnelB2_id').each(function() {
            $(this).html(choices);
            $(this).selectpicker('refresh');
            $(this).selectpicker('render');
        });
    });
    return false;
});

// Convert time as a string formatted as HH:MM
$('.duration').on('keyup', function() {
    var time_val = $(this).val();
    var time = time_val.replace(":", "");
    var number = Number(time).toString();
    if (number.length <= 4) {
        if (number.length == 1) {
           var time_str = '00:0'+number;
        } else if (number.length == 2) {
           var time_str = '00:'+number;
        } else if (number.length == 3) {
           time_str = '0'+number.slice(0,1)+":"+number.slice(1)
        } else {
            time_str = number.slice(0,2)+":"+number.slice(2)
        }
    } else {
        var time_str = time_val.slice(0,-1);
    }
    $(this).val(time_str);
});

$(document).off('click', '#calc_time');
$(document).on('click', '#calc_time', function (e) {
  e.preventDefault();
  console.log('calc_time clicked');

  const start  = $('#start_datetime').val();     // name="date", id="start_datetime"
  const finish = $('#finish_datetime').val();

  const drive  = $('#drive_duration').val()    || '00:00';
  const excl   = $('#excluded_duration').val() || '00:00';
  const wait   = $('#waiting_duration').val()  || '00:00';

  console.log('payload about to send:', {
    start_datetime: start,
    finish_datetime: finish,
    drive_time: drive,
    excluded_time: excl,
    waiting_time: wait
  });

  if (!start || !finish) {
    alert('Please select both Start and Finish date/times.');
    return;
  }

  $.getJSON('/bookings/calculate_times/', {
    date:  start,
    finish_datetime: finish,
    drive_time:      drive,
    excluded_time:   excl,
    waiting_time:    wait
  })
  .done(function (data) {
    $('#tt_duration').val(data.total_testifying_time);
    $('#tw_duration').val(data.total_work_time);
  })
  .fail(function (xhr) {
    console.error('AJAX failed', xhr.status, xhr.responseText);
  });
});