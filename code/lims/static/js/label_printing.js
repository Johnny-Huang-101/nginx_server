
/** README:
 * 
 * initTests()-- function is called when the page loads. It initializes the dymo label framework.
 * 
 * printLabelBtn -- Printing logic for mainly href elements throughout modules
 * 
 * ShowLoading and hideLoading -- functions to show and hide loading modal
 * 
 * submitBtnAutopsy -- Buttons for autopsy view
 * 
 * submitBtnHisto -- buttons for ADDING new containers and Specimen
 * 
 * submit BtnSaR -- logic for reagents and solvents are differnet since its a nested fetch call for label data from backend
 * 
 * 
 * tryPritning -- Same logic for all button clicks, actually checks for enviornment printer then submits the actual print job
 * 
 * 
 * General Logic:
 * 
 * 1. Attaches a click event listner to pritng label buttons
 * 
 * 2. When button is clicked:
 *  *    - Prevent default link behavior to backend in python flask
 *  *    - Fetches label data from the backend using the button's href attribute (Expects JSON RETURN MUST)
 *  *    - Using the retrieved PRINTER, LABEL, ETC information; Calls the printLabels function with the fetched data
 * 
 * NOTE: The data returned from backend is EITHER:
 *  * 1. A SINGLE TUPLE of label attributes, printer name, dual_printer, roll, and a URL to redirect to after printing.
 *  * 2. A list of TUPLES of label attributes, printer name, dual_printer, roll, and a URL to redirect to after printing.
 * 
 * 3. For each label in the data retrieved
 *  *    - Fetches the label template XML from the server using the template name
 *  *    - Loads the label template and populates it with the data from the backend
 *  *    - Prints the label using the specified printer and roll (if applicable)
 * 
 * 4. After printing, redirects to the specified URL (if provided) or reloads the page. If no URL is provided in JSON from backend then page stays
 */







function initTests() {
    if(dymo.label.framework.init) {
        //dymo.label.framework.trace = true;
        dymo.label.framework.init(onload);
    } else {
        onload();
    }
}

if (window.addEventListener)
window.addEventListener("load", initTests, false);
else if (window.attachEvent)
window.attachEvent("onload", initTests);
else
window.onload = initTests;


// PRINTING BUTTON MODULES (Batch constituents, tests, batches, specimen, standards and solutions, containers)
document.querySelectorAll(".printLabelBtn").forEach(button => {
    button.addEventListener("click", async function(event) {
        console.time("Total Execution Time");
        console.time("Fetch Label Data");

        const link = event.target.closest('.printLabelBtn');
        event.preventDefault();

        const clickedHref = link.getAttribute('href');
        console.log('Clicked href:', clickedHref);

        async function printLabels(data) {
            let labelAttributes = data[0]; 
            let printerName = data[1]; 
            let dual_printer = data[2] ?? false;
            let roll = data[3] ?? null;
            
            // roll = 1;
            // dual_printer = true;
            // printerName = '\\DYMO LabelWriter 450 Twin Turbo';
            const actualPath = printerName.replace(/\\\\/g, '\\');
            const lastSegment = actualPath.match(/[^\\]+$/)[0];
        
            const alternative = lastSegment;
        
            console.log("Received label data:", labelAttributes, "Using printer:", printerName, "Alternative:", alternative, "Dual Printer:", dual_printer, "Roll:", roll);
        
            for (const labelData of labelAttributes) {
                let templateName = labelData.template;
        
                console.time(`Fetch Label Template - ${templateName}`);
                try {
                    const response = await fetch(`/static/label_templates_xml/${templateName}.xml`);
                    const labelXml = await response.text();
                    console.timeEnd(`Fetch Label Template - ${templateName}`);
        
                    console.time(`Load and Populate Label - ${templateName}`);
                    let label = dymo.label.framework.openLabelXml(labelXml);
                    console.log(`Label ${templateName} is loaded!`);
        
                    for (const [key, value] of Object.entries(labelData)) {
                        if (key !== "template" && key !== "amount") {
                            label.setObjectText(key, value);
                        }
                    }
        
                    console.timeEnd(`Load and Populate Label - ${templateName}`);
        
                    console.time(`Print Label - ${templateName}`);
                    await tryPrinting(label, printerName, alternative, dual_printer, roll, labelData.amount);
                    console.timeEnd(`Print Label - ${templateName}`);
                } catch (error) {

                    if (error.name === "PrinterNotFoundError") {
                        alert(error.message);
                    }
                    else{
                        alert("An error occurred while printing labels. Please Contact FLD LIMS.");
                        console.error(`Error loading label template (${templateName}):`, error);
                    }
                    console.timeEnd(`Fetch Label Template - ${templateName}`);
                }
            }
        
            console.timeEnd("Total Execution Time");
        
            if (data[4]) {
                window.location.href = data[4];
            }
        }

        try {
            const response = await fetch(clickedHref);
            const data = await response.json();
            console.timeEnd("Fetch Label Data");

            await printLabels(data);  

        } catch (error) {
            alert("An error occurred while fetching label data. Please Contact FLD LIMS.");
            console.error("Error fetching label data:", error);
            console.timeEnd("Fetch Label Data");
            console.timeEnd("Total Execution Time");
        }
    });
});











function showLoading() {
    const modal = document.getElementById('loading-modal');
    if (modal) modal.style.display = 'flex';
}

function hideLoading() {
    const modal = document.getElementById('loading-modal');
    if (modal) modal.style.display = 'none';
}





//AUTOPSY 
document.querySelectorAll(".submitBtnAutopsy").forEach(button => {
button.addEventListener("click", function (e) {
    e.preventDefault();

    showLoading();
    console.time("Total Execution Time")
    

    let submit_buttons = {
        "submit_scan": "Submit",
        "submit_toxicology_print": "Print Autopsy",
        "submit_physical_print": "Print Admin Review/External",
        "submit_physical_sa_print": "Print Physical (SA)",
        "submit_bundle_print": "Print Homicide",
        "submit_histology_print": "Print Histology (T)",
        "submit_histology_sa_print": "Print Histology (S)",
        "submit_drug_print": "Print Drug",
        "submit_other_print": "Submit",
        "submit_generic_print": "Print Generic Label",
        "submit_histo_scan": "Submit",
        "submit_five_generic": "Print Generic (x5)"
    }


    // Get the action type from the button
    const action = this.dataset.action;

    // Grab the form element (or scope to the closest form if multiple forms)
    const form = this.closest('form');
    const formData = new FormData(form);

    // Append the clicked button's name and value
    formData.append(action, submit_buttons[action]);


    if (action === 'submit_scan') {

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
            '[id^="specOther"]',
        ];

        // Iterate through patterns and validate matching fields
        requiredFieldPatterns.forEach(function (pattern) {
          $(pattern).each(function () {
            const field = $(this);

            // Skip if this is the discipline-select dropdown
            if (field.is('#discipline-select') || field.attr('name') === 'discipline-select') {
              return true;  // continue to next element
            }

            const isSpecOther = field.is('[id^="specOther"]');

            // If it's a "-spec-other" field and it's disabled, skip validation entirely
            if (isSpecOther && field.is(':disabled')) {
              field.removeClass('is-invalid');
              return true;
            }

            // Otherwise, remove disabled so we can validate everything else
            field.prop('disabled', false);

            // Only validate fields that are <input> or <select>
            if (field.is('input, select')) {
              if (field.val() === '' || field.val() === null) {
                isValid = false;
                console.log(
                  'FAILED VALIDATION -',
                  'Name:', field.attr('name'),
                  'ID:',   field.attr('id'),
                  'Value:',field.val()
                );
                field.addClass('is-invalid');
              } else {
                field.removeClass('is-invalid');
              }
            }
          });
        });


        // Prevent form submission if validation fails
        if (!isValid) {
            e.preventDefault(); // Prevent form submission
            alert('Please fill in all required fields. And check Dates and Times.');
            hideLoading(); // Ensure loading indication is hidden
            return; // Prevent further execution
        }
    }

    console.log("Sending form data:", Object.fromEntries(formData));

    console.timeEnd("Fetch Label Data");
    fetch(`/autopsy_view`,{
        method: "POST",
        body: formData
        })
        .then(response => response.json())
        .then(data => {
            console.timeEnd("Fetch Label Data");

            // let printerName = data[1]; 
            // let labelAttributes = data[0]; 
            // let dual_printer = data[2] ? true : false;
            // let roll = data[3] ? 1 : null;

            
            async function printLabels(data) {
                
                console.log(data);
                if(data[0][0]===null){

                    if(data[0][4]){

                        console.log("Redirecting to URL:", data[0][4]);
                        window.location.href = data[0][4];
                    }

                    // window.location.reload();
                }

                for (let [labelAttributes, printerName, dual_printer, roll, url] of data) {
                    dual_printer = dual_printer ?? false;
                    roll = roll ?? null;
                    // dual_printer = true;
                    // roll = 1;
                    // printerName = '\\\\OCMEG9CM09.medex.sfgov.org\\DYMO LabelWriter 450 Twin Turbo (Copy 1)';
                    // printerName = '\\\\OCMEG9M012.medex.sfgov.org\\BS02 - Accessioning';
                    // printerName = 'DYMO LabelWriter 450 Twin Turbo';
                    // invPrinter = '\\\\OCMEG9M042.medex.sfgov.org\\DYMO LabelWriter 450 Turbo';
                    const actualPath = printerName.replace(/\\\\/g, '\\');
                    const alternative = actualPath.match(/[^\\]+$/)[0];
                    console.log("Received label data:", labelAttributes, "Using printer:", printerName, "Alternative:", alternative);
            
                    // Wait for all label templates to be processed in series
                    for (const labelData of labelAttributes) {
                        let templateName = labelData.template;
            
                        console.time(`Fetch Label Template - ${templateName}`);
            
                        try {
                            const labelXml = await fetch(`/static/label_templates_xml/${templateName}.xml`).then(response => response.text());
            
                            console.timeEnd(`Fetch Label Template - ${templateName}`);
            
                            console.time(`Load and Populate Label - ${templateName}`);
            
                            let label = dymo.label.framework.openLabelXml(labelXml);
            
                            for (const [key, value] of Object.entries(labelData)) {
                                if (key !== "template" && key !== "amount") {
                                    label.setObjectText(key, value);
                                }
                            }
            
                            console.timeEnd(`Load and Populate Label - ${templateName}`);
            
                            console.time(`Print Label - ${templateName}`);
                            // Uncomment to enable actual printing:
                            await tryPrinting(label, printerName, alternative, dual_printer, roll, labelData.amount);
                            console.timeEnd(`Print Label - ${templateName}`);
                        } catch (error) {

                            if (error.name === "PrinterNotFoundError") {
                                alert(error.message);
                            }
                            else{
                                alert("An error occurred while printing labels. Please Contact FLD LIMS.");
                                console.error(`Error loading label template (${templateName}):`, error);
                            }
                            console.timeEnd(`Fetch Label Template - ${templateName}`);
                        }
                    }
                    
                    if (url) {
                        window.location.href = url;
                    }
                }

                hideLoading();
                console.timeEnd("Total Execution Time");
                // window.location.reload();
            }
            
            // Call the function
            printLabels(data);
            

    
        })
        .catch(error => {
            console.error("Error fetching label data:", error);
            console.timeEnd("Fetch Label Data");
            console.timeEnd("Total Execution Time");
            alert("An error occurred while fetching label data. Please Contact FLD LIMS.");
            hideLoading(); // Ensure loading indication is hidden
        });
});
});








//AUTOPSY 
document.querySelectorAll(".submitBtnOther").forEach(button => {
button.addEventListener("click", function (e) {
    e.preventDefault();

    showLoading();
    console.time("Total Execution Time")
    

    let submit_buttons = {
        "submit_scan": "Submit",
        "submit_toxicology_print": "Print Autopsy",
        "submit_physical_print": "Print Admin Review/External",
        "submit_physical_sa_print": "Print Physical (SA)",
        "submit_bundle_print": "Print Homicide",
        "submit_histology_print": "Print Histology (T)",
        "submit_histology_sa_print": "Print Histology (S)",
        "submit_drug_print": "Print Drug",
        "submit_other_print": "Submit",
        "submit_generic_print": "Print Generic Label",
        "submit_histo_scan": "Submit",
        "submit_five_generic": "Print Generic (x5)"
    }


    // Get the action type from the button
    const action = this.dataset.action;

    // Grab the form element (or scope to the closest form if multiple forms)
    const form = this.closest('form');
    const formData = new FormData(form);

    // Append the clicked button's name and value
    formData.append(action, submit_buttons[action]);


    if (action === 'submit_scan') {

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
            '[id^="specOther"]',
        ];

        // Iterate through patterns and validate matching fields
        requiredFieldPatterns.forEach(function (pattern) {
          $(pattern).each(function () {
            const field = $(this);

            // Skip if this is the discipline-select dropdown
            if (field.is('#discipline-select') || field.attr('name') === 'discipline-select') {
              return true;  // continue to next element
            }

            const isSpecOther = field.is('[id^="specOther"]');

            // If it's a "-spec-other" field and it's disabled, skip validation entirely
            if (isSpecOther && field.is(':disabled')) {
              field.removeClass('is-invalid');
              return true;
            }

            // Otherwise, remove disabled so we can validate everything else
            field.prop('disabled', false);

            // Only validate fields that are <input> or <select>
            if (field.is('input, select')) {
              if (field.val() === '' || field.val() === null) {
                isValid = false;
                console.log(
                  'FAILED VALIDATION -',
                  'Name:', field.attr('name'),
                  'ID:',   field.attr('id'),
                  'Value:',field.val()
                );
                field.addClass('is-invalid');
              } else {
                field.removeClass('is-invalid');
              }
            }
          });
        });


        // Prevent form submission if validation fails
        if (!isValid) {
            e.preventDefault(); // Prevent form submission
            alert('Please fill in all required fields. And check Dates and Times.');
            hideLoading(); // Ensure loading indication is hidden
            return; // Prevent further execution
        }
    }

    console.log("Sending form data:", Object.fromEntries(formData));

    console.timeEnd("Fetch Label Data");
    fetch(`/autopsy_view`,{
        method: "POST",
        body: formData
        })
        .then(response => response.json())
        .then(data => {
            console.timeEnd("Fetch Label Data");

            // let printerName = data[1]; 
            // let labelAttributes = data[0]; 
            // let dual_printer = data[2] ? true : false;
            // let roll = data[3] ? 1 : null;

            
            async function printLabels(data) {
                
                console.log(data);
                if(data[0][0]===null){

                    if(data[0][4]){

                        console.log("Redirecting to URL:", data[0][4]);
                        window.location.href = data[0][4];
                    }

                    // window.location.reload();
                }

                for (let [labelAttributes, printerName, dual_printer, roll, url] of data) {
                    dual_printer = dual_printer ?? false;
                    roll = roll ?? null;
                    // dual_printer = true;
                    // roll = 1;
                    // printerName = '\\\\OCMEG9CM09.medex.sfgov.org\\DYMO LabelWriter 450 Twin Turbo (Copy 1)';
                    // printerName = '\\\\OCMEG9M012.medex.sfgov.org\\BS02 - Accessioning';
                    // printerName = 'DYMO LabelWriter 450 Twin Turbo';
                    // invPrinter = '\\\\OCMEG9M042.medex.sfgov.org\\DYMO LabelWriter 450 Turbo';
                    const actualPath = printerName.replace(/\\\\/g, '\\');
                    const alternative = actualPath.match(/[^\\]+$/)[0];
                    console.log("Received label data:", labelAttributes, "Using printer:", printerName, "Alternative:", alternative);
            
                    // Wait for all label templates to be processed in series
                    for (const labelData of labelAttributes) {
                        let templateName = labelData.template;
            
                        console.time(`Fetch Label Template - ${templateName}`);
            
                        try {
                            const labelXml = await fetch(`/static/label_templates_xml/${templateName}.xml`).then(response => response.text());
            
                            console.timeEnd(`Fetch Label Template - ${templateName}`);
            
                            console.time(`Load and Populate Label - ${templateName}`);
            
                            let label = dymo.label.framework.openLabelXml(labelXml);
            
                            for (const [key, value] of Object.entries(labelData)) {
                                if (key !== "template" && key !== "amount") {
                                    label.setObjectText(key, value);
                                }
                            }
            
                            console.timeEnd(`Load and Populate Label - ${templateName}`);
            
                            console.time(`Print Label - ${templateName}`);
                            // Uncomment to enable actual printing:
                            await tryPrinting(label, printerName, alternative, dual_printer, roll, labelData.amount);
                            console.timeEnd(`Print Label - ${templateName}`);
                        } catch (error) {

                            if (error.name === "PrinterNotFoundError") {
                                alert(error.message);
                            }
                            else{
                                alert("An error occurred while printing labels. Please Contact FLD LIMS.");
                                console.error(`Error loading label template (${templateName}):`, error);
                            }
                            console.timeEnd(`Fetch Label Template - ${templateName}`);
                        }
                    }
                    
                    if (url) {
                        window.location.href = url;
                    }
                    else{
                        window.location.reload();
                    }
                }

                hideLoading();
                console.timeEnd("Total Execution Time");
                // window.location.reload();
            }
            
            // Call the function
            printLabels(data);
            

    
        })
        .catch(error => {
            console.error("Error fetching label data:", error);
            console.timeEnd("Fetch Label Data");
            console.timeEnd("Total Execution Time");
            alert("An error occurred while fetching label data. Please Contact FLD LIMS.");
            hideLoading(); // Ensure loading indication is hidden
        });
});
});

//ADDING A NEW CONTAINER and specimen / HISTO For Investigators
document.querySelectorAll(".submitBtnHisto").forEach(button => {
    button.addEventListener("click", function (e) {
        e.preventDefault();
        $('#processing').modal('show');


        console.time("Total Executino Time");
        // Grab the form element (or scope to the closest form if multiple forms)
        const form = this.closest('form');
        const formData = new FormData(form);


        formData.append(button.getAttribute('name'), '1');
        // console.log("Sending form data:", Object.fromEntries(formData));
        
        let url = window.location.href;

        fetch(url,{
            method: "POST",
            body: formData
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(data => {
                        if (data.errors) {

                            alert("Please fill in all required fields. And check Dates and Times.");
                            // Highlight fields here
                            for (const [field, messages] of Object.entries(data.errors)) {
                                const input = form.querySelector(`[name=${field}]`);
                                if (input) {
                                    input.classList.add("is-invalid");
                            
                                    // Prevent stacking error messages
                                    if (!input.nextElementSibling || !input.nextElementSibling.classList.contains("invalid-feedback")) {
                                        const errorMsg = document.createElement("div");
                                        errorMsg.className = "invalid-feedback";
                                        errorMsg.innerText = messages.join(", ");
                                        input.after(errorMsg);
                                    }
                            
                                    const eventType = (input.tagName.toLowerCase() === 'select') ? 'change' : 'input';
                                    input.addEventListener(eventType, function handler() {
                                        if (input.value) {
                                            input.classList.remove("is-invalid");
                                            const feedback = input.nextElementSibling;
                                            if (feedback && feedback.classList.contains("invalid-feedback")) {
                                                feedback.remove();
                                            }
                                            input.removeEventListener(eventType, handler);
                                        }
                                    });
                                }
                            }                            
                        }
                        throw new Error("Validation failed");
                    });
                }
                return response.json();
            })
            .then(data => {
                console.timeEnd("Fetch Label Data");
                
                async function printLabels(data) {
                    try {
                        if (data[0][0] === null) {
                            if (data[0][4]) {
                                window.location.href = data[0][4];
                                return;
                            }
                        }
                
                        for (let [labelAttributes, printerName, dual_printer, roll, url] of data) {
                            dual_printer = dual_printer ?? false;
                            roll = roll ?? null;
                            
                            // printerName = 'DYMO LabelWriter 450 Twin Turbo';
                            const actualPath = printerName.replace(/\\\\/g, '\\');

                            // Extract the last part after the final backslash
                            const lastSegment = actualPath.match(/[^\\]+$/)[0];

                            let alternative;
                            if (lastSegment.endsWith('INV')) {
                                // Remove the last 3 characters (i.e., 'INV')
                                alternative = lastSegment.slice(0, -4);
                            } else {
                                alternative = lastSegment;
                            }

                            

                            console.log("Received label data:", labelAttributes, "Using printer:", printerName, "Alternative:", alternative);
                            for (const labelData of labelAttributes) {
                                let templateName = labelData.template;
                                const labelXml = await fetch(`/static/label_templates_xml/${templateName}.xml`).then(res => res.text());
                                let label = dymo.label.framework.openLabelXml(labelXml);
                
                                for (const [key, value] of Object.entries(labelData)) {
                                    if (key !== "template" && key !== "amount") {
                                        label.setObjectText(key, value);
                                    }
                                }
            
                                await tryPrinting(label, printerName, alternative, dual_printer, roll, labelData.amount);
                            }
                
                            if (url) {
                                window.location.href = url;
                            }
                        }
                
                        $('#processing').modal('hide');
                    } catch (error) {

                        if (error.name === "PrinterNotFoundError") {
                            alert(error.message);
                        }
                        else{
                            alert("An error occurred while printing labels. Please Contact FLD LIMS.");
                            console.error(`Error loading label template (${templateName}):`, error);
                        }
                        $('#processing').modal('hide');
                        // Stay on the page, no redirect
                    } finally {
                        console.timeEnd("Total Execution Time");
                    }
                }
                
                printLabels(data);

            })
            .catch(error => {
                console.error("Error fetching label data:", error);
                console.timeEnd("Fetch Label Data");
                console.timeEnd("Total Execution Time");
                
                if (error.message !== "Validation failed") {
                    alert("An error occurred while fetching label data. Please Contact FLD LIMS.");
                }
                $('#processing').modal('hide');
            });
    });
    });



// solvents and reagents
document.querySelectorAll(".submitBtnSaR").forEach(button => {
    button.addEventListener("click", function (e) {
        e.preventDefault();
        $('#processing').modal('show');

        console.time("Total Executino Time");
        let url = window.location.href;
        const form = this.closest('form');
        const formData = new FormData(form);

        fetch(url, {
            method: "POST",
            body: formData
        })
        .then(response => response.json())
        .then(data => {

            console.log("Data Received: ",data);
            console.timeEnd("Fetch Label Data");

            // Always follow the redirect URL if data[0] is null
            if (data[0][0] === null && data[0][4]) {
                fetch(data[0][4])
                    .then(res => res.json())
                    .then(actualLabelData => {
                        printLabels(actualLabelData);
                    })
                    .catch(err => {
                        console.error("Error fetching label data from redirected route:", err);
                        alert("An error occurred while printing labels. Please Contact FLD LIMS.");
                        $('#processing').modal('hide');
                    });
            } else {
                printLabels(data);
            }

            async function printLabels(data) {
                try {
                    for (let [labelAttributes, printerName, dual_printer, roll, url] of data) {
                        dual_printer = dual_printer ?? false;
                        roll = roll ?? null;
                        // printerName = 'DYMO LabelWriter 450 Twin Turbo';
                        // roll = 1;
                        // dual_printer = true;

                        const actualPath = printerName.replace(/\\\\/g, '\\');
                        const lastSegment = actualPath.match(/[^\\]+$/)[0];
                        const alternative = lastSegment;

                        console.log("Received label data:", labelAttributes, "Using printer:", printerName, "Alternative:", alternative);

                        for (const labelData of labelAttributes) {
                            const templateName = labelData.template;
                            const labelXml = await fetch(`/static/label_templates_xml/${templateName}.xml`).then(res => res.text());
                            const label = dymo.label.framework.openLabelXml(labelXml);

                            for (const [key, value] of Object.entries(labelData)) {
                                if (key !== "template" && key !== "amount") {
                                    label.setObjectText(key, value);
                                }
                            }

                            await tryPrinting(label, printerName, alternative, dual_printer, roll, labelData.amount);
                        }

                        if (url) {
                            window.location.href = url;
                        }
                    }

                    $('#processing').modal('hide');
                } catch (error) {

                    if (error.name === "PrinterNotFoundError") {
                        alert(error.message);
                    }
                    else{
                        alert("An error occurred while printing labels. Please Contact FLD LIMS.");
                        console.error(`Error loading label template (${templateName}):`, error);
                    }
                    $('#processing').modal('hide');
                } finally {
                    console.timeEnd("Total Execution Time");
                }
            }
        })
        .catch(error => {
            console.error("Error fetching label data:", error);
            console.timeEnd("Fetch Label Data");
            console.timeEnd("Total Execution Time");
            alert("An error occurred while fetching label data. Please Contact FLD LIMS.");
            $('#processing').modal('hide');
        });
    });
});

$(document).on("click", ".submitBtnStockJar", function () {

    showLoading();
    var selectedRow = $('#autopsy_view tbody tr.selected');
    var caseId = selectedRow.find('td:nth-child(2)').text().trim(); // 2nd column = case number

    fetch('/stock_jar', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({case_id: caseId})
    })
    .then(response => response.json())
    .then(data => {
        console.timeEnd("Fetch Label Data");
            async function printLabels(data) {
                
                console.log(data);
                if(data[0][0]===null){

                    if(data[0][4]){

                        console.log("Redirecting to URL:", data[0][4]);
                        window.location.href = data[0][4];
                    }

                    // window.location.reload();
                }

                for (let [labelAttributes, printerName, dual_printer, roll, url] of data) {
                    dual_printer = dual_printer ?? false;
                    roll = roll ?? null;
                    // dual_printer = true;
                    // roll = 1;
                    // printerName = '\\\\OCMEG9CM09.medex.sfgov.org\\DYMO LabelWriter 450 Twin Turbo (Copy 1)';
                    // printerName = '\\\\OCMEG9M012.medex.sfgov.org\\BS02 - Accessioning';
                    // printerName = 'DYMO LabelWriter 450 Twin Turbo';
                    // invPrinter = '\\\\OCMEG9M042.medex.sfgov.org\\DYMO LabelWriter 450 Turbo';
                    const actualPath = printerName.replace(/\\\\/g, '\\');
                    const alternative = actualPath.match(/[^\\]+$/)[0];
                    console.log("Received label data:", labelAttributes, "Using printer:", printerName, "Alternative:", alternative);
            
                    // Wait for all label templates to be processed in series
                    for (const labelData of labelAttributes) {
                        let templateName = labelData.template;
            
                        console.time(`Fetch Label Template - ${templateName}`);
            
                        try {
                            const labelXml = await fetch(`/static/label_templates_xml/${templateName}.xml`).then(response => response.text());
            
                            console.timeEnd(`Fetch Label Template - ${templateName}`);
            
                            console.time(`Load and Populate Label - ${templateName}`);
            
                            let label = dymo.label.framework.openLabelXml(labelXml);
            
                            for (const [key, value] of Object.entries(labelData)) {
                                if (key !== "template" && key !== "amount") {
                                    label.setObjectText(key, value);
                                }
                            }
            
                            console.timeEnd(`Load and Populate Label - ${templateName}`);
            
                            console.time(`Print Label - ${templateName}`);
                            // Uncomment to enable actual printing:
                            await tryPrinting(label, printerName, alternative, dual_printer, roll, labelData.amount);
                            console.timeEnd(`Print Label - ${templateName}`);
                        } catch (error) {

                            if (error.name === "PrinterNotFoundError") {
                                alert(error.message);
                            }
                            else{
                                alert("An error occurred while printing labels. Please Contact FLD LIMS.");
                                console.error(`Error loading label template (${templateName}):`, error);
                            }
                            console.timeEnd(`Fetch Label Template - ${templateName}`);
                            hideLoading();
                        }
                    }
                    
                    if (url) {
                        window.location.href = url;
                    }
                }

                hideLoading();
                console.timeEnd("Total Execution Time");
                // window.location.reload();
            }
            
            // Call the function
            printLabels(data);
    })
    .catch(error => console.error("Error printing Stock Jar:", error));
});

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////



function tryPrinting(label, printerName, alternative, dual_printer, roll, amount) {
const printers = dymo.label.framework.getPrinters();
var segment = window.location.pathname.split('/')[1]

// console.log("YES ", amount);
let printerFound = false;
let alternativePrinterFound = false;

// Check if the specified printer is in the list
for (const printer of printers) {
    if (printer.name === printerName) {
        printerFound = true;
    }

    if(printer.name === alternative) {
        alternativePrinterFound = true;
    }
}

console.log(printerFound, alternativePrinterFound)
if (!printerFound && !alternativePrinterFound) {
    console.log(`Printer "${printerName}" not found. Trying to add the printer and retry printing.`);
    const printerErrorMessage = `
    Printer "${printerName}" Not Found.
    The "${segment}" item may still have been added to the database, please check before resubmitting the form.
    Please connect your printer by doing the following:
        1. Using Windows Search bar, enter " Printers & scanners".
        2. Click "Add Device".
        2. Select "Add Device" for a printer called "${printerName}".
        3. Retry printing your label. If the printer still isn't connected this message will reappear!
    Contact FLD if the instructions above does not resolve your issue.
    `;

    const error = new Error(printerErrorMessage);
    error.name = "PrinterNotFoundError";
    throw error;
} else {

    // Printer found, print the label

    if (dual_printer){

        let dict = {}

        if (roll == 0) {
            dict['twinTurboRoll'] = dymo.label.framework.TwinTurboRoll.Left;
        } else if (roll == 1) {
            dict['twinTurboRoll'] = dymo.label.framework.TwinTurboRoll.Right;
        } else if (roll == 2) {
            dict['twinTurboRoll'] = dymo.label.framework.TwinTurboRoll.Auto;
        }
        let printParamsXml = dymo.label.framework.createLabelWriterPrintParamsXml(dict);

        if(printerFound){
            label.print(printerName, printParamsXml); // no contorl for amount or verbosity
            console.log("Printing on network!");
        }
        else{
            label.print(alternative, printParamsXml); // no contorl for amount or verbosity
            console.log("Printing on Local!");
        }
    }
    else{
        if(printerFound){
            label.print(printerName); // no contorl for amount or verbosity
            console.log("Printing on network ONCE!");
        }
        else{
            label.print(alternative); // no contorl for amount or verbosity
            console.log("Printing on Local!");
        }
    }



    console.log("Label has been successfully printed!");
}
}
