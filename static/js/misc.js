var currentPlayer;
var currentButton;
function EvalSound(soundobj, button)
{
    var thissound = document.getElementById(soundobj);
    if(currentPlayer  && currentPlayer !== thissound)
    {
        currentPlayer.pause();
        $(currentButton).find(".glyphicon").removeClass("glyphicon-pause").addClass("glyphicon-play");
    }
    if (thissound.paused)
    {
        thissound.play();
        currentPlayer = thissound;
        currentButton = button;
         if ($(button).find(".glyphicon").hasClass("glyphicon-play"))
         {
             $(button).find(".glyphicon").removeClass("glyphicon-play").addClass("glyphicon-pause");
         }
         else {$(button).find(".glyphicon").removeClass("glyphicon-pause").addClass("glyphicon-play");}
    }
    else
    {
        thissound.pause();
        $(button).find(".glyphicon").removeClass("glyphicon-pause").addClass("glyphicon-play");
    }
}
