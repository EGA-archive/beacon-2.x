(function(){ // scoping


    // ----------------------------------------------
    // Join target-selection to result-selection
    // ----------------------------------------------

    var targetInstance = $("#target-instance");

    // define result-option-complex html chunks
    function updateOptions(selectedTarget) {
        var dataTarget = selectedTarget.attr("data-target");

        var individualChunk = "<div><input id='individual' type='radio' name='result-option' class='result-option' value='individual'> <label for='individual'>Show individual</label></div><div><input id='sample' type='radio' name='result-option' class='result-option' value='sample'> <label for='sample'>Show samples from individual</label></div><div><input id='variant' type='radio' name='result-option' class='result-option' value='variant'> <label for='variant'>Show variants from individual</label></div>"
        var sampleChunk = "<div><input id='sample' type='radio' name='result-option' class='result-option' value='sample'> <label for='sample'>Show sample</label></div><div><input id='individual'  type='radio' name='result-option' class='result-option' value='individual'> <label for='individual'>Show individual</label></div><div><input id='variant' type='radio' name='result-option' class='result-option' value='variant'> <label for='variant'>Show variants in sample</label></div>"
        var variantChunk = "<div><input id='variant' type='radio' name='result-option' class='result-option' value='variant'> <label for='variant'>Show variant</label></div><div><input id='individual' type='radio' name='result-option' class='result-option' value='individual'> <label for='individual'>Show individuals with variant</label></div><div><input id='sample' type='radio' name='result-option' class='result-option' value='sample'> <label for='sample'>Show samples with variant</label></div>"
    
        // change result-option-complex 
        var optionsWrapper = $("#options-wrapper");
        if (dataTarget == "individual") {optionsWrapper.html(individualChunk)} 
        else if (dataTarget == "sample") {optionsWrapper.html(sampleChunk)} 
        else if (dataTarget == "variant") {optionsWrapper.html(variantChunk)};

        // set targetInstance value
        targetInstance.val(dataTarget);
    };

    // set at the beginning
    $("#result-option-all").attr("value", $(".target-icon.active").attr("data-target"));
    updateOptions($(".target-icon.active"));
    
    // set when user clicks
    $("#target-selection").on("click",".target-icon", function(){
        var dataTarget = $(this).attr("data-target");

        // deselect all and select this
        $(".target-icon").removeClass("active");
        $(this).addClass("active");

        // set result-selection-all target
        $("#result-option-all").attr("value", dataTarget);

        // call function to update result-selection-complex options
        updateOptions($(this));

    });


    // ----------------------------------------------
    // search all or complex
    // ----------------------------------------------
    $(".result-selection").on("click", function(){
        $(".result-selection").removeClass("active");
        $(this).addClass("active");

        if ($(this).is("#result-selection-complex")) {
            $("#result-selection-all .result-option").prop("checked", false);
        } else if ($(this).is("#result-selection-all")) {
            $("#result-selection-complex .result-option").prop("checked", false);
            $("#result-selection-all .result-option").prop("checked", true);
        };
    });

})();
