function EvalSound(soundobj, button) {
    var thissound = document.getElementById(soundobj);
    if (thissound.paused) {
      thissound.play();
      $(button).find(".glyphicon").removeClass("glyphicon-play").addClass("glyphicon-play");
    } else {
      thissound.pause();
      $(button).find(".glyphicon").removeClass("glyphicon-pause").addClass("glyphicon-pause");
    }
  }