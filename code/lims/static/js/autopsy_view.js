// Show the loading modal when the page starts loading
    // window.addEventListener('beforeunload', function () {
    //     document.getElementById('loading-modal').style.display = 'flex';
    // });

    // // Hide the loading modal once the page has fully loaded
    // document.addEventListener('DOMContentLoaded', function () {
    //     document.getElementById('loading-modal').style.display = 'none';
    // });

$(document).ready(function () {
    // Function to check if any rows have the class "selected"
    function toggleButtons() {
        if ($('tr.selected').length > 0) {
            // Enable buttons if any rows are selected
            $('#submit_toxicology_print, #submit_physical_print, #submit_physical_sa_print, #submit_bundle_print, #submit_histology_print, #submit_histology_sa_print, #submit_drug_print, #submit_generic_print, #other-labels, #submit-specimens, #submit_five_generic').prop('disabled', false);
        } else {
            // Disable buttons if no rows are selected
            $('#submit_toxicology_print, #submit_physical_print, #submit_physical_sa_print, #submit_bundle_print, #submit_histology_print, #submit_histology_sa_print, #submit_drug_print, #submit_generic_print, #other-labels, #submit-specimens, #submit_five_generic').prop('disabled', true);
        }
    }

    // Initially call the toggle function to set the correct button state
    toggleButtons();

    // When a row is clicked, ensure only one row is selected at a time or unselect it if clicked again
    $('tr').click(function () {
        // Ignore the click if it's on a header row (inside <thead>)
        if ($(this).closest('thead').length > 0) {
            return;  // Exit if it's a header row
        }

        // If the row is already selected, unselect it and reset the select field
        if ($(this).hasClass('selected')) {
            $(this).removeClass('selected');
            $('#cases_selected').val(0);  // Reset the select field to 0
        } else {
            // Remove the 'selected' class from all rows
            $('tr').removeClass('selected');

            // Add the 'selected' class to the clicked row
            $(this).addClass('selected');

            // Get the value from column 0 (first column) of the clicked row
            let caseValue = $(this).find('td:first').text().trim();

            // Set the selected case value in the select field
            $('#cases_selected').val(caseValue);
        }

        toggleButtons();  // Check button state after toggling selection
    });
});

$(function () {
    // Load specimen types dynamically on discipline change
    $('#specimen_discipline').on('change', function () {
        const discipline = $(this).val();
        const container = $('#specimen_type_checkboxes');
        container.empty();

        $.getJSON('/cases/get_specimen_types/', { discipline }, function (data) {
            for (const item of data.choices) {
                const row = $(`
                    <div class="form-row align-items-center mb-2">
                        <div class="d-flex align-items-center" style="width: 100%; height: 90%">
                            <input type="checkbox" name="specimen_type" value="${item.id}" id="specimen_type_${item.id}" style="display:none">
                                <label for="specimen_type_${item.id}" class="specimen-click-label mr-3" style="cursor:pointer; margin: 0;">
                                    <strong>[${item.code}]</strong> ${item.name}
                                </label>
                            <input type="number" class="form-control form-control-sm specimen-qty ml-auto" name="specimen_quantity_${item.id}" min="0" value="0" style="width: 80px;">
                        </div>
                    </div>
                `);
                container.append(row);
            }

            // Toggle checkbox when label is clicked
            container.find('.specimen-click-label').on('click', function () {
                const forId = $(this).attr('for');
                const checkbox = $('#' + forId);
                checkbox.prop('checked', !checkbox.prop('checked'));
                $(this).toggleClass('active');
            });

            // Filter checkboxes by search text
            $('#specimen_type_search').on('keyup', function () {
                const query = $(this).val().toLowerCase();
                $('#specimen_type_checkboxes .form-row').each(function () {
                    const labelText = $(this).find('.specimen-click-label').text().toLowerCase();
                    $(this).toggle(labelText.includes(query));
                });
            });
        });
    });
});


$(function () {
    let selected = [];

    // When user clicks "Print" on the first modal
    $('#confirm-other-print').on('click', function () {
        selected = [];

        $('#specimen_type_checkboxes input[type="number"]').each(function () {
            const qty = parseInt($(this).val(), 10);
            const label = $(this).closest('.form-row').find('.specimen-click-label').text().trim();

            if (qty > 0) {
                selected.push({ label, qty });
            }
        });

        if (selected.length === 0) {
            alert("Please select at least one specimen with a quantity > 0.");
            return;
        }

        const caseNumber = $('#modal-case-number').text().trim();

        // Build modal confirmation content
        let message = `<div>Confirm Labels for <strong>Case #${caseNumber}</strong><br><br>`;
        message += `Are you sure you want to generate the following <strong>initial</strong> labels?<ul>`;
        for (const item of selected) {
            message += `<li>${item.qty}:   ${item.label}</li>`;
        }
        message += `</ul></div>`;

        $('#confirm-modal-body').html(message);
        $('#confirm_modal').modal('show');
    });

    // $(document).on('click', '[data-toggle="modal"][data-target="#other_label_select"]', function () {
    //     const caseNumber = $(this).data('case-number');
    //     $('#modal-case-number').text(caseNumber);
    // });

});






$(document).ready(function () {




    function addNewSpecimenRow() {
        // Get the last barcode input field
        let lastBarcode = $('.form-control[id^="barcode"]').last();
        let lastId = lastBarcode.attr('id'); // e.g., "barcode1"
        let lastNum = parseInt(lastId.match(/\d+$/)); // Extract number part

        // Calculate the next number
        let nextNum = lastNum + 1;

        // Create the new row HTML
        let newRow = `
            <hr style="border-top: 2px solid #ccc">
            <div class="row" id="row-${nextNum}">
                <div class="col">
                    <label for="barcode${nextNum}" style="font-weight: bold">Specimen QR Code:</label>
                    <input type="text" id="barcode${nextNum}" class="form-control" name="barcode${nextNum}">
                    <i class="bi bi-dash-square text-danger delete-row" style="cursor: pointer;" title="Remove row"></i>
                </div>
                <div class="col">
                    <label for="container${nextNum}" style="font-weight: bold">Container:</label><br>
                    <select id="container${nextNum}" name="container${nextNum}" class="form-control selectpicker" data-size="5"></select>
                </div>
                <div class="col">
                    <label for="discipline${nextNum}" style="font-weight: bold">Discipline:</label><br>
                    <select id="discipline${nextNum}" name="discipline${nextNum}" class="form-control selectpicker" data-size="5"></select>
                </div>
                <div class="col">
                    <label for="collectionVessel${nextNum}" style="font-weight: bold">Collection Vessel:</label><br>
                    <select id="collectionVessel${nextNum}" name="collectionVessel${nextNum}" class="form-control selectpicker" data-size="5"></select>
                </div>
                <div class="col-sm-1">
                    <label for="amount${nextNum}" style="font-weight: bold">Amount:</label>
                    <input type="text" id="amount${nextNum}" name="amount${nextNum}" class="form-control">
                </div>
                <div class="col">
                    <label for="condition${nextNum}" style="font-weight: bold">Condition:</label><br>
                    <select id="condition${nextNum}" name="condition${nextNum}" class="form-control selectpicker" multiple data-live-search="true" data-size="5"></select>
                </div>
                <div class="col">
                    <label for="collectionDate${nextNum}" style="font-weight: bold">Collection Date:</label>
                    <input type="date" id="collectionDate${nextNum}" name="collectionDate${nextNum}" class="form-control">
                </div>
                <div class="col">
                    <label for="collectionTime${nextNum}" style="font-weight: bold">Collection Time:</label>
                    <input type="text" id="collectionTime${nextNum}" name="collectionTime${nextNum}" class="form-control">
                </div>
                <div class="col-sm-1">
                    <label for="collectedBy${nextNum}" style="font-weight: bold">Collected By:</label><br>
                    <select id="collectedBy${nextNum}" name='collectedBy${nextNum}' class="form-control selectpicker" data-live-search="true" data-size="5"></select>
                </div>
            </div>
            <div class="row" id="row-${nextNum}-spec-other">
                <div class="col">
                    <label for="specOther${nextNum}" style="font-weight: bold">Other Description</label>
                    <input type="text" id="specOther${nextNum}" name="specOther${nextNum}" class="form-control" disabled>
                </div>
            </div>
            <div class="row" id="row-${nextNum}-custody">
                <div class="col">
                    <label for="custodyLocation${nextNum}" style="font-weight: bold">Custody Location Type:</label><br>
                    <select id="custodyLocation${nextNum}" name="custodyLocation${nextNum}" class="form-control selectpicker" data-live-search="true" data-size="5"></select>
                </div>
                <div class="col">
                    <label for="custody${nextNum}" style="font-weight: bold">Custody:</label><br>
                    <select id="custody${nextNum}" name="custody${nextNum}" class="form-control selectpicker" data-live-search="true" data-size="5"></select>
                    <br>
                    <i class="bi bi-arrow-clockwise text-primary refresh-row" style="cursor: pointer;" title="Refresh matching rows"></i>
                </div>
            </div>
            <hr style="border-top: 2px solid #ccc">
        `;

        // Append it after the last <hr>
        $('hr').last().after(newRow);
        $('.selectpicker').selectpicker('refresh');
    }

    $(document).on('click', '#add-specimen', function () {
        addNewSpecimenRow();
    });


    // Listen for changes on any barcode input field
    $(document).on('change', '.form-control[id^="barcode"]', function () {
        let barcodeInput = $(this); // The barcode input that triggered the change
        let rowId = barcodeInput.attr('id').match(/\d+$/)[0]; // Extract the row number (e.g., "1", "2", etc.)
        let barcodeValue = barcodeInput.val(); // Get the entered barcode value
        let caseId = $('#cases_selected').val();

        // Send a GET request to /cases/sample
        $.getJSON("/cases/get_submission_data", { barcode: barcodeValue, case_id: caseId }, function (response) {
            if (response.error) {
                alert(response.error);
            } else if (response) {
                // Create a sort order for collectors based on personnel job_title
                const priorityTitles = [
                    "Forensic Autopsy Technician",
                    "Assistant Medical Examiner",
                    "Chief Medical Examiner"
                ];
                const sortedCollectors = response.collector_choices.sort((collectorA, collectorB) => {
                    // 0 if job_title is in the priority list, 1 otherwise
                    const aPriority = priorityTitles.includes(collectorA.job_title) ? 0 : 1;
                    const bPriority = priorityTitles.includes(collectorB.job_title) ? 0 : 1;
                    // Put priority titles first, then alphabetical by name
                    return aPriority - bPriority || collectorA.name.localeCompare(collectorB.name);
                });
                    
                // Update dropdown choices for the row first
                updateDropdown(`#discipline${rowId}`, response.discipline_choices);
                updateDropdown(`#container${rowId}`, response.container_choices);
                updateDropdown(`#collectionVessel${rowId}`, response.vessel_choices);
                updateDropdown(`#condition${rowId}`, response.condition_choices);
                $(`#condition${rowId}`).selectpicker('refresh');
                updateDropdown(`#collectedBy${rowId}`, sortedCollectors);
                updateDropdown(`#custodyLocation${rowId}`, response.location_choices);
                updateDropdown(`#custody${rowId}`, response.custody_choices);

                // Set the values for associated elements
                $(`#barcode${rowId}`).val(response.specimen_type);
                $(`#discipline${rowId}`).selectpicker('val', response.discipline);
                $(`#container${rowId}`).selectpicker('val', response.container);
                $(`#collectionVessel${rowId}`).selectpicker('val', response.collection_vessel);
                $(`#custodyLocation${rowId}`).selectpicker('val', response.default_location);
                $(`#custody${rowId}`).selectpicker('val', response.default_custody);

                // Conditional: if barcode value contains 'Tissue', set amount to 1.
                if ($(`#barcode${rowId}`).val().includes("Tissue")) {
                    $(`#amount${rowId}`).val(1);
                } else {
                    $(`#amount${rowId}`).val("");
                }

                // Conditional: if barcode value contains 'Other', enable the specOther field.
                if ($(`#barcode${rowId}`).val().indexOf("Other") !== -1) {
                    $(`#specOther${rowId}`).prop('disabled', false);
                } else {
                    $(`#specOther${rowId}`).prop('disabled', true);
                }

                $(`#custody${rowId}`).parent().find('.dropdown-toggle').css({
                    'pointer-events': 'none',
                    'background-color': '#e9ecef',
                    'opacity': '0.8'
                });

                $(`#custodyLocation${rowId}`).parent().find('.dropdown-toggle').css({
                    'pointer-events': 'none',
                    'background-color': '#e9ecef',
                    'opacity': '0.8'
                });
            }
        });

        addNewSpecimenRow();
    });

    // Function to update a dropdown with new options
    function updateDropdown(selector, choices) {
        let dropdown = $(selector);
        dropdown.empty(); // Clear existing options
        choices.forEach(choice => {
            dropdown.append(`<option value="${choice.id}">${choice.name}</option>`);
        });
        dropdown.selectpicker('refresh');
    }

    // Listen for clicks on the delete icon to remove the row
    $(document).on('click', '.delete-row', function () {
        // Find the current row being deleted
        const currentRow = $(this).closest('div[id^="row-"]');

        // Determine the ID of the current row
        const currentRowId = currentRow.attr('id');

        // Remove the current row and its associated custody row
        const custodyRowId = currentRowId + '-custody';
        const specOtherRowId = currentRowId + '-spec-other';
        currentRow.next('hr').remove(); // Remove the associated <hr> element
        currentRow.remove(); // Remove the current row
        $('#' + custodyRowId).remove(); // Remove the associated custody row
        $('#' + specOtherRowId).remove(); // Remove the associated custody row
    });


    $(document).on('click', '.refresh-row', function () {
        const parentRow = $(this).closest('.row'); // Get the parent row of the clicked icon
        const rowIdMatch = parentRow.attr('id').match(/row-(\d+)(-custody)?$/); // Match row ID pattern
        const rowId = rowIdMatch ? rowIdMatch[1] : null; // Extract the row number

        if (!rowId) {
            console.warn("Failed to extract row ID.");
            return; // Exit if row ID cannot be determined
        }

        const containerValue = $(`#container${rowId}`).val(); // Get the container value

        if (!containerValue) {
            console.warn("No container selected for the triggering row.");
            return; // Exit early if no value is selected
        }

        const collectionDate = $(`#collectionDate${rowId}`).val();
        const collectionTime = $(`#collectionTime${rowId}`).val();
        const collectedBy = $(`#collectedBy${rowId}`).val();

        console.log(`Refreshing rows: containerValue = ${containerValue}`);

        // Update all rows with the matching container value
        $(`select[name^="container"]`).each(function () {
            const thisContainer = $(this).val();
            console.log(`Checking container: thisContainer = ${thisContainer}`);

            if (String(thisContainer) === String(containerValue)) {
                const currentRowIdMatch = $(this).attr('id').match(/container(\d+)$/);
                const currentRowId = currentRowIdMatch ? currentRowIdMatch[1] : null;

                if (currentRowId) {
                    console.log(`Updating row ${currentRowId} for matching container: ${thisContainer}`);
                    $(`#collectionDate${currentRowId}`).val(collectionDate);
                    $(`#collectionTime${currentRowId}`).val(collectionTime);
                    $(`#collectedBy${currentRowId}`).val(collectedBy).selectpicker('refresh');
                }
            }
        });
    });


    $(document).on('click', '#cancel-submit-specimens', function () {
        // Remove all dynamically added rows (exclude the first row and row-1-custody)
        $('div[id^="row-"]').not('#row-1').not('#row-1-custody').next('hr').remove(); // Remove associated hr elements
        $('div[id^="row-"]').not('#row-1').not('#row-1-custody').remove(); // Remove dynamically added rows

        // Clear data in the first row
        $('#row-1 .form-control').val('');
        $('#row-1 .selectpicker').val('').selectpicker('refresh');
        $('#row-1-custody .form-control').val('');
        $('#row-1-custody .selectpicker').val('').selectpicker('refresh');
    });

    $(document).on('change', 'select[id^="custodyLocation"]', function () {
        const custodyLocationSelect = $(this); // The custodyLocation dropdown that triggered the change
        const rowId = custodyLocationSelect.attr('id').match(/\d+$/)[0]; // Extract the row number
        const locationType = custodyLocationSelect.val(); // Get the selected value from custodyLocation

        // Send a GET request to locations/get_location_ids
        $.getJSON('/locations/get_location_ids/', {
            location_table: locationType,
        }, function(data) {
            var options = '';
            for (var item of data.choices) {
                options += '<option value="' + item.id + '">' + item.name + '</option>';
            }

            $(`#custody${rowId}`).html(options);
            $(`#custody${rowId}`).selectpicker('refresh');
            $(`#custody${rowId}`).selectpicker('render');
            $(`#custody${rowId}`).selectpicker('val', '');
            $(`#custody${rowId}`).selectpicker('refresh');

        });
    });
});



$(document).on('change', 'select[id^="custodyLocation"], select[id^="custody"]', function () {
    const changedElement = $(this); // The custodyLocation or custody dropdown that triggered the change
    const rowIdMatch = changedElement.attr('id').match(/\d+$/); // Extract the row number
    const rowId = rowIdMatch ? rowIdMatch[0] : null;

    if (!rowId) {
        console.warn("Failed to extract row ID from changed element.");
        return; // Exit if row ID cannot be determined
    }

    const containerValue = $(`#container${rowId}`).val(); // Get the container value for the current row

    if (!containerValue) {
        console.warn("No container value found for the triggering row.");
        return; // Exit if no container value is found
    }

    // Get the new custodyLocation and custody values
    const newCustodyLocation = $(`#custodyLocation${rowId}`).val();
    const newCustody = $(`#custody${rowId}`).val();

    // Update all rows with the same container value
    $(`select[name^="container"]`).each(function () {
        const thisContainer = $(this).val();
        const currentRowIdMatch = $(this).attr('id').match(/\d+$/); // Extract the row number
        const currentRowId = currentRowIdMatch ? currentRowIdMatch[0] : null;

        if (String(thisContainer) === String(containerValue) && currentRowId) {
            console.log(`Updating row ${currentRowId} for matching container: ${thisContainer}`);
            // Only update custodyLocation and make the GET request if the new value is different
            if (newCustodyLocation !== $(`#custodyLocation${currentRowId}`).val()) {
                $(`#custodyLocation${currentRowId}`).val(newCustodyLocation).selectpicker('refresh');

                // Send a GET request to locations/get_location_ids
                $.getJSON('/locations/get_location_ids/', {
                    location_table: newCustodyLocation,
                }, function(data) {
                    var options = '';
                    for (var item of data.choices) {
                        options += '<option value="' + item.id + '">' + item.name + '</option>';
                    }

                    $(`#custody${currentRowId}`).html(options);
                    $(`#custody${currentRowId}`).selectpicker('refresh');
                    $(`#custody${currentRowId}`).selectpicker('render');
                    $(`#custody${currentRowId}`).selectpicker('val', '');
                    $(`#custody${currentRowId}`).selectpicker('refresh');
                });
            }
            $(`#custody${currentRowId}`).val(newCustody).selectpicker('refresh');
        }
    });
});

$(document).ready(function () {
    // Attach a submit event handler to the form
    $('form').on('submit', function (e) {

        // Check if the submit button clicked has the ID "submit_scan"
        const clickedButton = document.activeElement; // The element that triggered the event
        if (!clickedButton || clickedButton.id !== 'submit_scan') {
            return; // Exit if it's not the submit button with the specified ID
        }

        let isValid = true;

        // Define field patterns
        const requiredFieldPatterns = [
            '[id^="barcode"]',          // All fields starting with "barcode"
            '[id^="container"]',        // All fields starting with "container"
            '[id^="discipline"]',       // All fields starting with "discipline"
            '[id^="collectionVessel"]', // All fields starting with "collectionVessel"
            '[id^="amount"]',           // All fields starting with "amount"
            '[id^="collectionDate"]',   // All fields starting with "collectionDate"
            '[id^="collectionTime"]',   // All fields starting with "collectionTime"
            '[id^="collectedBy"]',      // All fields starting with "collectedBy"
            '[id^="custodyLocation"]',  // All fields starting with "custodyLocation"
            '[id^="custody"]',          // All fields starting with "custody"
        ];

        // Iterate through patterns and validate matching fields
        requiredFieldPatterns.forEach(function (pattern) {
            $(pattern).each(function () {
                const field = $(this);

                // Remove disabled attribute from all fields before validation
                field.prop('disabled', false);

                // Only validate fields that are <input> or <select>
                if (field.is('input, select')) {
                    if (field.val() === '' || field.val() === null) {
                        isValid = false;
                        console.log('FAILED VALIDATION - Name:', field.attr('name'), 'ID:', field.attr('id'), 'Value:', field.val());
                        field.addClass('is-invalid'); // Add a red border or visual cue
                    } else {
                        field.removeClass('is-invalid'); // Remove the red border if valid
                    }
                }
            });
        });

        // Prevent form submission if validation fails
        if (!isValid) {
            e.preventDefault(); // Prevent form submission
            alert('Please fill in all required fields.');
        }
    });
});