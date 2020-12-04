(function(){ // scoping


    // ----------------------------------------------
    // Join target-selection to result-selection
    // ----------------------------------------------

    var targetInstance = $("#target-instance");

    // define result-option-complex html chunks
    function updateOptions(selectedTarget) {
        var dataTarget = selectedTarget.attr("data-target");
    
        // change result-option-complex 
        var optionsWrapperAll = $(".options-wrapper");
        optionsWrapperAll.removeClass("active");

        var optionsWrapperIndividual = $(".options-wrapper#individual-options");
        var optionsWrapperSample = $(".options-wrapper#sample-options");
        var optionsWrapperVariant = $(".options-wrapper#variant-options");

        if (dataTarget == "individual") {optionsWrapperIndividual.addClass("active")} 
        else if (dataTarget == "sample") {optionsWrapperSample.addClass("active")} 
        else if (dataTarget == "variant") {optionsWrapperVariant.addClass("active")};

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

        // reset targetId and resultOptions
        $("#targetId").val("");
        $("#result-selection-complex .result-option").prop("checked", false);
    });


    // ----------------------------------------------
    // search all or complex
    // ----------------------------------------------
    $(".result-selection").on("click", function(){
        $(".result-selection").removeClass("active");
        $(this).addClass("active");

        if ($(this).is("#result-selection-complex")) {
            $("#result-selection-all .result-option").prop("checked", false);
            $("#result-selection-complex input").attr("required", true);

        } else if ($(this).is("#result-selection-all")) {
            $("#result-selection-complex .result-option").prop("checked", false);
            $("#result-selection-all .result-option").prop("checked", true);
            $("#result-selection-complex input").val("");
            $("#result-selection-complex input").attr("required", false);
        };
    });


    // ----------------------------------------------
    // Extra info
    // ----------------------------------------------

    var mainTable = $("#main-result");
    var extraInfo = $("#extra-info");

   
    mainTable.on("click", "td.extra-info-trigger", function(){
        // update content
        var me = $(this);
        var extraInfoHTML = me.siblings("td.hidden").html();
        extraInfo.html(extraInfoHTML);
        // for closing
        extraInfo.on("click", "i.close-button", function(){
            extraInfo.addClass("hidden");
            me.parent().removeClass("active");
        });
        // make side panel visible
        extraInfo.removeClass("hidden");
        // highlight row
        mainTable.find("tr").removeClass("active");
        me.parent().addClass("active");
    });



})();
