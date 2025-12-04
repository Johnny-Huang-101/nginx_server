// When compounds are selected, the unique drug classes of those compounds will be
// concatenated with " / " and the ranks that have been used for this component drug
// class will be displayed.

    $('#compound_id').on('change', function () {
        compound_id = $(this).val().join(", ");
        console.log(compound_id)
        if (compound_id) {
         $.getJSON('/components/get_drug_classes/', {
            compound_id: compound_id
            }, function(data) {
                if (data.rank_str) {
                 $('#rank-str').html(data.rank_str+ " currently used for ")
                } else {
                 $('#rank-str').html("No ranks for ")
                }
                $('#drug-class').html(data.drug_class + ' <i class="fa-solid fa-circle-plus"></i>')
                $('#drug-class-name').html(data.drug_class)

                rank_html = ""
                for (rank of data.ranks) {
                rank_html += rank[0]+'. '+rank[1]+'<br>'
                }

                if (rank_html) {
                    $('#ranks').html(rank_html);
                } else {
                    $('#ranks').html("No ranks to display");
                }
            });
            return false;
         } else {
            $('#rank-str').html("")
            $('#drug-class').html("")
            $('#ranks').html("");
         }
    });
