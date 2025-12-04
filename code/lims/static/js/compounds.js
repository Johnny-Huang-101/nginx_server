
// Make request to https://opsin.ch.cam.ac.uk/ using entered iupac name to get
// cas_no., formula, mass, inchikey, smiles and the structure.
// Additionally, synonyms from PubChem are show in result_id for structural confirmation

  $("#get-identifiers").on('click', function() {
    // unhide the fetching identifiers spinner
    $('#fetching-identifiers').attr('hidden', false)
    // Get the iupac value
    iupac = $("#iupac").val()
    // Set the form fields for iteration
    var fields = ['cas_no', 'formula', 'mass', 'inchikey', 'smiles']

    $.getJSON('/compounds/get_identifiers', {
      iupac: iupac,
    }, function(data) {

    // Set the error value under each of the fields
    $(".error").text(data.error);
    // Set the values of the fields
    // If a value is already in the field, add it in green text below
    for (var field of fields) {
        console.log(field)
        console.log(data[field])
        if ($('#'+field).val()) {
            if ($('#'+field).val() != data[field]) {
                $('#'+field).siblings('div').children().append('<p style="color:green">Suggested: '+data[field]+'</p')
            }
        } else {
            $('#'+field).val(data[field]);
        }
    }

      // Unhide div and display structure
      $('#structure-div').attr('hidden', false)
      $("#structure").attr("src", data.structure);
      // Display identifers/aliases
      $("#identifiers").text(data.identifiers);
      // Set url to PubChem
      $('#pubchem-url').attr('href', 'https://pubchem.ncbi.nlm.nih.gov/#query='+data.inchikey)
      // Hide the fetching identifiers text
      $('#fetching-identifiers').attr('hidden', true)

    });
    return false;
  });

//// Same as above except on every key stroke
//  $("#iupac").on('keyup', function() {
//    $('#fetching-identifiers').attr('hidden', false)
//    var fields = ['cas_no', 'formula', 'mass', 'inchikey', 'smiles']
//    $.getJSON('/compounds/get_identifiers', {
//      iupac: $("#iupac").val(),
//    }, function(data) {
//    console.log(data.entries)
//    for (var field of fields) {
//        console.log(field)
//        console.log(data[field])
//        if ($('#'+field).val()) {
//            if ($('#'+field).val() != data[field]) {
//                $('#'+field).siblings('div').children('.error').text(data[field])
//            }
//        } else {
//            $('#'+field).val(data[field]);
//        }
//    }
//
////      $("#formula").val(data.formula);
////      $("#mass").val(data.mass);
////      $("#inchikey").val(data.inchikey);
////      $("#smiles").val(data.smiles);
//      $("#structure").attr("src", data.structure);
//      $("#result_id").text(data.result_id);
//      if (data.error){
//        $(".error").text(data.error);
//      }
//      $('#fetching-identifiers').attr('hidden', true)
//    });
//    return false;
//  });


