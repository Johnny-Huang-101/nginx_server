// Get the current URL
var currentUrl = window.location.href;

// Split the URL by '/'
var urlParts = currentUrl.split('batches/');

// Extract the item_id (assuming it's the third segment in the URL)
var item_id = urlParts[1].split('/')[0];

// Now you can use item_id in your JavaScript logic
console.log('item_id:', item_id);

$(document).ready(function(){
    // Handle input in #sourceScan and fetch batch information
    $('#sourceScan').on('change', function() {
        var inputValue = $(this).val();
        var batchFunc = $('#type').data('value');
        console.log('FUNCTION', batchFunc);

        $.ajax({
            url: '/batches/get_batch_information/',
            method: 'GET',
            data: { input: inputValue, item_id: item_id, batch_func: batchFunc },
            dataType: 'json',
            cache: true,  // Allow browser caching
            timeout: 10000, // Set a 3-second timeout
            success: function(data) {
                console.log('FUNCTION TRIGGER');
                $('#table tr.dynamic-row').remove();

                if (data.tests) {
                    $('#table').append(data.tests);
                    $('#source_name').text(data.source_out.specimen);
                }

                console.log(data.source_out);
            },
            error: function(xhr, status, error) {
                console.error('Error:', error);
                $('#table tr.dynamic-row').remove();
            }
        });

    });

    // Listen for input changes on all inputs with id starting with "testScan"
    $('#table').on('change', 'input[id^="testScan"]', function() {
        // Get the id of the current input element
        var inputId = $(this).attr('id');

        // Extract the number from the input id (assuming the format is "testScan#")
        var index = inputId.replace('testScan', '');

        // Construct the corresponding td id based on the extracted index
        var testTestId = 'sourceName' + index;

        // Find the corresponding td element using the constructed id
        var expectedValue = $('#' + testTestId).data('value').toString();

        var inputFull = $(this).val();

        // Get the value entered in the input and extract the part after ": "
         var splitInput = inputFull.split(": ");
         var inputValue = (splitInput.length > 1) ? splitInput[1] : inputFull; // If there's no ": ", use inputFull



        console.log(inputFull);

        // Check if the input value matches the data-value
        if (inputValue === expectedValue) {
            console.log('Match found!');
            // You can also add some visual feedback here if needed, e.g., changing the color
            $('#' + testTestId).css('background-color', '#d4edda'); // Light green background
        } else {
            console.log('No match.', inputValue, expectedValue);
            // Reset any visual feedback
            $('#' + testTestId).css('background-color', '');
        }
        // Check if the input matches the qr_reference pattern
        if (/^qr_reference: \d+$/.test(inputFull)) {
            console.log('QR reference detected. Submitting the form...');
            $('#form').submit(); // Automatically submit the form
            return; // Stop further execution if qr_reference is detected
        }

        // Check all rows and submit the form if all match
        checkAllRowsAndSubmit();
    });

    // Function to check if all rows match and submit the form if they do
    function checkAllRowsAndSubmit() {
        var allMatch = true;

        // Iterate through each dynamically added row
        $('#table tr.dynamic-row').each(function() {
            // Get the index from the input's id
            var inputId = $(this).find('input[id^="testScan"]').attr('id');
            if (inputId) {
                var index = inputId.replace('testScan', '');

                // Construct the corresponding td id and get the expected value
                var testTestId = 'sourceName' + index;
                var expectedValue = $('#' + testTestId).data('value').toString();

                // Get the value from the input
                var splitInput = $(this).find('input').val().split(": ");

                // If the split was successful (there's a ": "), take the part after it, otherwise use the full input value
                var inputValue = (splitInput.length > 1) ? splitInput[1] : $(this).find('input').val();


                // If any row doesn't match, set allMatch to false
                if (inputValue !== expectedValue) {
                    allMatch = false;
                    return false; // Exit the loop early if a mismatch is found
                }
            }
        });

        // If all rows match, submit the form
        if (allMatch) {
            console.log('All rows match! Submitting the form...');
            $('#form').submit();
        }
    }
    // Show all rows
    $('#showAll').on('click', function() {
        $('#testsTable tbody tr').show();
    });

    // Hide rows with completed specimen check
    function hideCompleted() {
    // Select all rows in the table, including hidden ones
    $('#testsTable tbody tr').each(function() {
        var specimenCheck = $(this).data('specimen-check');

        // Hide rows where specimenCheck is not 'None' or 'Skipped'
        if (specimenCheck !== 'None' && specimenCheck !== 'Skipped') {
            $(this).hide(); // Hide completed rows
        } else {
            $(this).show(); // Show rows that match the condition
        }
    });
}

    // Hide completed rows
    $('#hideCompleted').on('click', function() {
        hideCompleted();
    });

    function sortAndHideRows() {
        // Get all rows in the table
        var rows = $('#testsTable tbody tr');

        // Filter rows that have a completed specimen-check (NOT 'None' or 'Skipped')
        var filteredRows = rows.filter(function() {
            var specimenCheck = $(this).data('specimen-check');
            return specimenCheck !== 'None' && specimenCheck !== 'Skipped';
        });

        // Show rows with completed specimen checks
        rows.each(function() {
            var specimenCheck = $(this).data('specimen-check');
            if (specimenCheck !== 'None' && specimenCheck !== 'Skipped') {
                $(this).show();
            } else {
                $(this).hide();
            }
        });

        // Sort the filtered rows by check-date (most recent first)
        var sortedRows = filteredRows.sort(function(a, b) {
            var dateA = new Date($(a).data('check-date')); // Convert check-date to Date object
            var dateB = new Date($(b).data('check-date'));
            return dateB - dateA; // Sort in descending order
        });

        // Append the sorted rows back to the table
        $('#testsTable tbody').append(sortedRows);
    }


    // Hide completed rows
    $('#showCompleted').on('click', function() {
        console.log('CLICK');
        sortAndHideRows();
    });

    // Hide complete rows on window load
    window.onload(sortAndHideRows());

});



//$(document).ready(function () {
//    // Source values
//    const sourceInput = $("#sourceScan").get(0);
//    const sourceTrueValue = $('#source').data('value');
//    // Test values
//    const testInput1 = $("#testScan1").get(0);
//    if (('#testScan1').includes(':')) {
//        const testInput1 = $('#testScan1').get(0);
//    } else {
//        const testInput1 = $('#testScan1').val();
//    }
//    const testTrueValue1 = $('#test1').data('value');
//    const testInput2 = $("#testScan2").get(0); // This element might not exist
//    const testTrueValue2 = testInput2 ? $('#test2').data('value') : null;
//
//    // Add an event listener for the source input if it exists
//    if (sourceInput) {
//        $(sourceInput).on('input', function() {
//            const inputValue = sourceInput.value;
//            if (inputValue !== sourceTrueValue) {
//                $('#sourceScan').removeClass('table-success').addClass('table-danger');
//            } else {
//                $('#sourceScan').removeClass('table-danger').addClass('table-success');
//            }
//            console.log("Source Input Change - TRUE VALUE:", sourceTrueValue);
//            console.log("Source Input Change - Current Value:", inputValue);
//            checkAndSubmitForm(); // Check and submit the form after each input
//        });
//    } else {
//        console.log("sourceInput does not exist.");
//    }
//
//    // Add an event listener for test input1 if it exists
//    if (testInput1) {
//        $(testInput1).on('input', function() {
//            const inputValue = testInput1.value;
//            if (inputValue !== testTrueValue1) {
//                $('#testScan1').removeClass('table-success').addClass('table-danger');
//            } else {
//                $('#testScan1').removeClass('table-danger').addClass('table-success');
//            }
//            console.log("Test Input1 Change - TRUE VALUE:", testTrueValue1);
//            console.log("Test Input1 Change - Current Value:", inputValue);
//            checkAndSubmitForm(); // Check and submit the form after each input
//        });
//    } else {
//        console.log("testInput1 does not exist.");
//    }
//
//    // Add an event listener for test input2 if it exists
//    if (testInput2) {
//        $(testInput2).on('input', function() {
//            const inputValue = testInput2.value;
//            if (inputValue !== testTrueValue2) {
//                $('#testScan2').removeClass('table-success').addClass('table-danger');
//            } else {
//                $('#testScan2').removeClass('table-danger').addClass('table-success');
//            }
//            console.log("Test Input2 Change - TRUE VALUE:", testTrueValue2);
//            console.log("Test Input2 Change - Current Value:", inputValue);
//            checkAndSubmitForm(); // Check and submit the form after each input
//        });
//    } else {
//        console.log("testInput2 does not exist.");
//    }
//
//    // Function to check inputs and submit the form if conditions are met
//    function checkAndSubmitForm() {
//        const sourceValue = sourceInput ? sourceInput.value : null;
//        const testValue1 = testInput1 ? testInput1.value : null;
//        const qrReferenceRegex = /^qr_reference: \d+$/;
//        console.log("Checking form submission conditions...");
//        console.log("sourceValue:", sourceValue, "sourceTrueValue:", sourceTrueValue);
//        console.log("testValue1:", testValue1, "testTrueValue1:", testTrueValue1);
//
//        if (testInput2) {
//            const testValue2 = testInput2.value;
//            console.log("testValue2:", testValue2, "testTrueValue2:", testTrueValue2);
//            if ((sourceValue === sourceTrueValue && testValue1 === testTrueValue1 && testValue2 === testTrueValue2) ||
//                qrReferenceRegex.test(sourceValue) || qrReferenceRegex.test(testValue1) || qrReferenceRegex.test(testValue2)) {
//                console.log("All conditions met. Submitting the form...");
//                $('#form').submit();
//            }
//        } else {
//            if ((sourceValue === sourceTrueValue && testValue1 === testTrueValue1) ||
//                qrReferenceRegex.test(sourceValue) || qrReferenceRegex.test(testValue1)) {
//                console.log("Conditions met without testInput2. Submitting the form...");
//                $('#form').submit();
//            }
//        }
//    }
//});