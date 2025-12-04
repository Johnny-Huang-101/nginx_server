const urlParams = new URLSearchParams(window.location.search);
const isHistology = urlParams.get('histology') === 'True';
console.log('HISTO', isHistology)

function handleDisciplineChange() {
    const discipline = $('#discipline').val()
    $.getJSON('/specimens/get_specimen_types/', {
            discipline: discipline,
            }, function(data) {
                var options = '';
                for (var item of data.choices) {
                    options += '<option value="' + item.id + '">' + item.name + '</option>';
                }

                $('#specimen_type_id').html(options)
                $('#specimen_type_id').selectpicker('refresh')
                $('#specimen_type_id').selectpicker('render')

            });
            return false;
}

$('#discipline').on('change', handleDisciplineChange)


 function setCurrentTime() {
    // Get the current time
    const now = new Date();
    const hours = String(now.getHours()).padStart(2, '0'); // Zero-pad hours
    const minutes = String(now.getMinutes()).padStart(2, '0'); // Zero-pad minutes

    // Format the time as HH:mm (e.g., 14:30)
    const currentTime = `${hours}${minutes}`;

    // Set the value of the collection_time field
    $('#collection_time').val(currentTime);
}

$('#case_id').on('change', function() {
    var case_id = $(this).val()
     $.getJSON('/specimens/get_containers/', {
        case_id: case_id,
        }, function(data) {
            console.log(data)
            var containers = '';
            for (let item of data.containers) {
                containers += '<option value="' + item.id + '">' + item.name + '</option>';
            }

            $('#container_id').html(containers);
            $('#container_id').selectpicker('refresh');
            $('#container_id').selectpicker('render');

            collectors = ""
            for (var item of data.collectors) {
                collectors += '<option value="' + item.id + '">' + item.name + '</option>';
            }

            $('#collected_by').html(collectors);
            $('#collected_by').selectpicker('refresh');
            $('#collected_by').selectpicker('render');

            if (data.collected_by) {
                $('#collected_by').attr('disabled', false)
                $('#no_collected_by').attr('disabled', false)
            } else {
                $('#collected_by').attr('disabled', true)
                $('#no_collected_by').attr('disabled', true)
            }

            $('#collected_by').selectpicker('refresh')
        });
        return false;
});


//$('#container_id').on('change', function() {
//    var container_id = $(this).val();
//    console.log(container_id)
//    $.getJSON('/specimens/get_collectors/', {
//        container_id: container_id,
//        }, function(data) {
//
//        if (data.collectors.length) {
//            var collectors = "";
//            for (var item of data.collectors) {
//                collectors += '<option value="' + item.id + '">' + item.name + '</option>';
//            }
//
//            $('#collected_by').html(collectors);
//            $('#collected_by').selectpicker('refresh');
//            $('#collected_by').selectpicker('render');
//
//            if (data.collected_by) {
//                $('#collected_by').attr('disabled', false)
//                $('#no_collected_by').attr('disabled', false)
//            } else {
//                $('#collected_by').attr('disabled', true)
//                $('#no_collected_by').attr('disabled', true)
//            }
//            $('#collected_by').selectpicker('refresh')
//        }
//        });
//        return false;
//});


//$('#specimen_type_id').on('change', function() {
//    var specimen_type_id = document.getElementById("specimen_type_id").value;
//    $.getJSON('/specimens/get_specimen_type_defaults/', {
//        specimen_type_id: specimen_type_id,
//        }, function(data) {
//            $('#collection_container_id').val(data.default_collection_container);
//            $('#collection_container_id').selectpicker('refresh');
//            $('#specimen-units').html(data.default_units)
//    });
//    return false;
//});

function handleSpecimenTypeChange() {
    var specimen_type_id = document.getElementById("specimen_type_id").value;
     $.getJSON('/specimens/get_specimen_type_defaults/', {
        specimen_type_id: specimen_type_id,
        }, function(data) {
            $('#collection_container_id').val(data.default_collection_container);
            $('#collection_container_id').selectpicker('refresh');
            $('#specimen-units').html(data.default_units)

            // Show or hide the #other-specimen element based on data.other
            if (data.other) {
                $('#other-specimen').css('display', 'block'); // or use .css('display', 'block');
            } else {
                $('#other-specimen').css('display', 'none'); // or use .css('display', 'none');
            }

            if (data.location_type) {
                $('#custody_type').val(data.location_type)
                $('#custody_type').selectpicker('refresh');

            }

            if (data.choices) {
                let options = '';
                for (var item of data.choices) {
                    options += '<option value="' + item.id + '">' + item.name + '</option>';
                }

                $('#custody').html(options);
                $('#custody').selectpicker('refresh');
                $('#custody').selectpicker('render');
                $('#custody').selectpicker('val', " ");

                if (data.default_location) {
                    $('#custody').selectpicker('val', data.default_location);
                    $('#custody').selectpicker('refresh');
                }
            }
        });
        return false;
};

if (window.location.href.includes('add')) {
  window.addEventListener('load', handleSpecimenTypeChange);
}

function checkSpecimenType() {
    var specimen_type_id = document.getElementById("specimen_type_id").value;
     $.getJSON('/specimens/get_specimen_type_defaults/', {
        specimen_type_id: specimen_type_id,
        }, function(data) {

            // Show or hide the #other-specimen element based on data.other
            if (data.other) {
                $('#other-specimen').css('display', 'block'); // or use .css('display', 'block');
            } else {
                $('#other-specimen').css('display', 'none'); // or use .css('display', 'none');
            }
        });
        return false;
};

$('#specimen_type_id').on('change', handleSpecimenTypeChange)

$(document).ready(function() {
    checkSpecimenType();
});

$(function() {
      $('#custody_type').on('change', function() {
         custody_type = $('#custody_type').val();
//         if (custody_type == 'Evidence Lockers') {
//            $('#locker-layout').attr('hidden', false)
//         } else {
//            $('#locker-layout').attr('hidden', true)
//         }
         $.getJSON('/specimens/get_custody_locations/', {
            custody_type: custody_type,
            }, function(data) {
                var options = '';
                for (var item of data.choices) {
                    options += '<option value="' + item.id + '">' + item.name + '</option>';
                }
                $('#custody').html(options)
                $('#custody').selectpicker('refresh')
                $('#custody').selectpicker('render')
                $('#custody').selectpicker('val', data.default_choice)
            });
            return false;
      });
});

$(function() {
    $('#admin_custody_type').on('change', function() {
        custody_type = $('#admin_custody_type').val();
//         if (custody_type == 'Evidence Lockers') {
//            $('#locker-layout').attr('hidden', false)
//         } else {
//            $('#locker-layout').attr('hidden', true)
//         }
        $.getJSON('/specimens/get_custody_locations/', {
        custody_type: custody_type,
        }, function(data) {
            var options = '';
            for (var item of data.choices) {
                options += '<option value="' + item.id + '">' + item.name + '</option>';
            }
            $('#admin_custody').html(options)
            $('#admin_custody').selectpicker('refresh')
            $('#admin_custody').selectpicker('render')
            $('#admin_custody').selectpicker('val', data.default_choice)
        });
        return false;
    });
});

$('#no_collected_by').on('click', function () {
    var checked = $(this).prop('checked')
    console.log(checked)
     if (checked) {
        $('#collected_by').attr('disabled', true)
        $('#collected_by').val(0)
    } else {
        $('#collected_by').attr('disabled', false)
    }

    $('#collected_by').selectpicker('refresh')
})


// Disable the submitted_sample_amount field if the unknown_sample_amount field is checked
function disableSubmittedSampleAmount() {
    var checked = $('#unknown_sample_amount').prop('checked')
     if (checked) {
        $('#submitted_sample_amount').attr('disabled', true)
    } else {
        $('#submitted_sample_amount').attr('disabled', false)
    }
}
$('#unknown_sample_amount').on('click', disableSubmittedSampleAmount)
//$(document).ready(disableSubmittedSampleAmount)



// Disable the unknown_sample_amount field when the submitted_sample_amount field contains data
function disableUnknownSampleAmount() {
    var sampleAmount = $('#submitted_sample_amount').val()
    if (sampleAmount) {
        $('#unknown_sample_amount').attr('disabled', true)
    } else {
        $('#unknown_sample_amount').attr('disabled', false)
    }
}

$('#submitted_sample_amount').on('keyup', disableUnknownSampleAmount)
$(document).ready(disableUnknownSampleAmount)


$(document).ready(function() {
    $('#parent_specimen').attr('disabled', false);
    var checked_load = $('#sub_specimen').prop('checked')
    console.log('CHECKED LOAD', checked_load)
    if (!checked_load) {
        $('#parent_specimen').closest('.bootstrap-select').find('.dropdown-toggle').css({
            'pointer-events': 'none',
            'background-color': '#e9ecef',
            'opacity': '0.8'
        });
        $('#parent_specimen').selectpicker('refresh');
    }
});



if (!isHistology) {
    $('#sub_specimen').on('click', function () {
        var checked = $(this).prop('checked');
        if (checked) {
            // Enable parent_specimen visually
            $('#parent_specimen').closest('.bootstrap-select').find('.dropdown-toggle').css({
                'pointer-events': 'auto',
                'background-color': '#fff',
                'opacity': '1'
            });
            $('#parent_specimen').selectpicker('refresh');

            // Disable container_id visually
            $('#container_id').closest('.bootstrap-select').find('.dropdown-toggle').css({
                'pointer-events': 'none',
                'background-color': '#e9ecef',
                'opacity': '0.8'
            });
            $('#container_id').selectpicker('refresh');
        } else {
            // Disable parent_specimen visually
            $('#parent_specimen').closest('.bootstrap-select').find('.dropdown-toggle').css({
                'pointer-events': 'none',
                'background-color': '#e9ecef',
                'opacity': '0.8'
            });
            $('#parent_specimen').val(0);
            $('#parent_specimen').selectpicker('refresh');

            // Enable container_id visually
            $('#container_id').closest('.bootstrap-select').find('.dropdown-toggle').css({
                'pointer-events': 'auto',
                'background-color': '#fff',
                'opacity': '1'
            });
            $('#container_id').selectpicker('refresh');
        }
    });
    
    
    
    
    

    function handleCaseIdChange() {
        var case_id = $('#case_id').prop('value');
        console.log('CASE ID', case_id);
        if (case_id && case_id !== '0') {
            $('#sub_specimen').attr('disabled', false);
            $.getJSON('/cases/get_specimens/', {
                case_id: case_id,
            }, function(data) {
                var options = '';
                for (var item of data.choices) {
                    options += '<option value="' + item.id + '">' + item.name + '</option>';
                }
                console.log('OPTIONS', options);
                $('#parent_specimen').html(options);
                $('#parent_specimen').selectpicker('refresh');
                $('#parent_specimen').selectpicker('render');
                $('#parent_specimen').selectpicker('val', data.default_choice);
            });
        } else {
            $('#parent_specimen').closest('.bootstrap-select').find('.dropdown-toggle').css({
                'pointer-events': 'none',
                'background-color': '#e9ecef',
                'opacity': '0.8'
            });
            $('#parent_specimen').val(0);
            $('#parent_specimen').selectpicker('refresh');
        }
    }

    function handleParentSpecimenChange() {
        // This is the actual specimen ID
        var parent_specimen = $('#parent_specimen').prop('value');
        console.log('parent_specimen', parent_specimen);
        if (parent_specimen && parent_specimen !== '0') {
            $.getJSON('/specimens/get_containers/', {
                 parent_specimen: parent_specimen, // Pass the parent_specimen to the backend
            }, function(data) {
                // Assuming the server returns the correct container ID directly
                if (data && data.container_id) {
                    // Set values and refresh selectpickers if needed
                    $('#container_id').selectpicker('val', data.container_id);
                    $('#container_id').selectpicker('refresh');
                    $('#discipline').selectpicker('val', data.discipline);
                    $('#discipline').selectpicker('refresh');
                    handleDisciplineChange()
                    setTimeout(function() {
                        $('#specimen_type_id').selectpicker('val', data.type_id);
                        $('#specimen_type_id').selectpicker('refresh');
                    }, 300);
                    setCurrentTime()
                    setTimeout(function() {
                        $('#collection_container_id').selectpicker('val', data.collection_vessel);
                        $('#collection_container_id').selectpicker('refresh');
                    }, 500);
                } else {
                    console.error('No matching container ID found in response');
                    $('#container_id').selectpicker('val', 0); // Reset to default if no match
                    $('#container_id').selectpicker('refresh');
                }
            });
        } else {
            $('#container_id').selectpicker('val', 0); // Reset to default when parent_specimen is invalid
            $('#container_id').selectpicker('refresh');
        }
    }

    // Run on change
    $('#case_id').on('change', handleCaseIdChange);
    $('#parent_specimen').on('change', handleParentSpecimenChange);


    // Run on table load
    $(document).ready(function () {
//        handleCaseIdChange();
        const discipline = $('#discipline').val();
        const specimenTypeId = $('#specimen_type_id').val();
        console.log('discipline: ',discipline)
        console.log('specimenTypeId: ',specimenTypeId)
        if (discipline && specimenTypeId ==0){
           handleDisciplineChange();
        }
    });
}


function disableCollectionDate() {
    //disable the collection date field if the no collection date check box
    // is checked
    var checked = $('#no_collection_date').prop('checked')

    if (checked) {
        $('#collection_date').prop('disabled', true)
        $('#collection_date').val("")
        $('#future_collection_date').prop('disabled', true)
    } else {
        $('#collection_date').prop('disabled', false)
        $('#future_collection_date').prop('disabled', false)
    }
}
// run script on page render and on click event
$('#no_collection_date').on('click', disableCollectionDate)

function disableCollectionTime() {
    //disable the collection time field if the no collection time check box
    // is checked
    var checked = $('#no_collection_time').prop('checked')

    if (checked) {
        $('#collection_time').prop('disabled', true)
        $('#collection_time').val("")
    } else {
        $('#collection_time').prop('disabled', false)
    }
}

// run script on page render and on click event
$('#no_collection_time').on('click', disableCollectionTime)



$('#future_collection_date').on('click', function () {
    console.log($(this).prop('checked'))
    if ($(this).prop('checked')) {
        $('#no_collection_date').attr('disabled', true)
    } else {
        $('#no_collection_date').attr('disabled', false)
    }
})

$(document).ready(function () {
    console.log("Pending fields: ", pending_fields)
    console.log("Approved fields: ", approved_fields)
    console.log('Function: ', func)
    if (['Edit', 'Approve'].includes(func)) {

        // Disable the no_collection_date_field if collection_date is neither in pending or approved_fields
        if (approved_fields.length && !pending_fields.includes('collection_date') && !approved_fields.includes('collection_date')) {
            $('#no_collection_date').attr('disabled', true)
        }

        // Disable the no_collection_time field if collection_time is neither in pending or approved_fields
        if (approved_fields.length && !pending_fields.includes('collection_time') && !approved_fields.includes('collection_time')) {
            $('#no_collection_time').attr('disabled', true)
        }

        // Disable the unknown_sample_amount field if submitted_sample_amount is neither in pending or approved_fields
        if (!pending_fields.includes('submitted_sample_amount') && !approved_fields.includes('submitted_sample_amount')) {
            $('#unknown_sample_amount').attr('disabled', true)
        }

        // Disable the no_collected_by field if collected_by is an approved field
        if (!pending_fields.includes('collected_by') && !approved_fields.includes('collected_by')) {
            $('#no_collected_by').attr('disabled', true)
        }

        if (approved_fields.includes('collection_date')) {
            $('#no_collection_date').attr('disabled', true)
        }

        if (approved_fields.includes('collection_time')) {
            $('#no_collection_time').attr('disabled', true)
        }

        if (approved_fields.includes('collection_date') && approved_fields.includes('collection_time')) {
            $('#collection_date').attr('disabled', true)
            $('#collection_time').attr('disabled', true)
            $('#no_collection_date').attr('disabled', true)
            $('#no_collection_time').attr('disabled', true)
            $('#future_collection_date').attr('disabled', true)
        }
    }
})

// Re-enable all checkboxes on form submit, otherwise their data will be False
$('#form').on('submit', function() {
    $('#no_collection_date').attr('disabled', false)
    $('#no_collection_time').attr('disabled', false)
    $('#future_collection_date').attr('disabled', false)
    $('#unknown_sample_amount').attr('disabled', false)
    $('#no_collected_by').attr('disabled', false)
});

$(document).ready(function () {
    // Check if 'from_autopsy=True' is present in the URL
    const urlParams = new URLSearchParams(window.location.search);
    const fromAutopsy = urlParams.get('from_autopsy') === 'True';

    if (fromAutopsy) {
        const exitAnchor = $('#exit');

        if (exitAnchor.length) {
            // Use the URL passed from Flask
            exitAnchor.attr('href', autopsyViewUrl);
            console.log(`Exit link updated to: ${autopsyViewUrl}`);
        } else {
            console.error('Anchor element with id "exit" not found');
        }
    } else {
        console.log('from_autopsy parameter is not present or not true in the URL');
    }
});

